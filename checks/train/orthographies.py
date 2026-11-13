"""Build Font Check's second set of orthographies (checks/language_orthographies.json): the languages
Hyperglot does not describe, from other open sources, each row saying where it comes from.

Hyperglot (checks/train/languages.py, checks/language_coverage.json) stays the first choice: a
language it describes is taken from it alone, in the scripts it gives; a declared source below may
add a script it does not give the language in (second_scripts), as may a keyboard layout. A language
Hyperglot describes through its members, by Glottolog's classification (Akan, through Twi and
Fante), gets no row of its own. A language it lacks is taken from the first declared
source below that has it, and from that one alone (every script it gives): a declared orthography
is never mixed with anything. A language no declared source has is taken from the inferred sources,
all of those that have it (REINFORCED below says how they are put together), in this order:

Declared (a person or a maintained project states the characters):

1. Google Fonts' language data (googlefonts/lang, "gflanguages"; Apache License 2.0): exemplar
   characters (base, auxiliary, marks), autonyms, populations.
2. Unicode CLDR (Unicode License V3): each locale's main and auxiliary exemplar characters.
3. SIL's Locale Data Repository (silnrsi/sldr; MIT License): the same, for many more languages, at
   the draft level SLDR gives each (approved, contributed, provisional, unconfirmed, proposed).

Inferred (the characters a text uses, counted; not an orthography anyone declared):

4. SLDR's exemplars at draft level "generated": SIL's own tools made them (from the texts SIL
   holds); they are taken as SLDR gives them.
5. Unilex (unicode-org/unilex; Unicode License V3): word frequencies of crawled corpora. Counted
   here, by the rule below.
6. An Crubadan (Kevin Scannell's corpora of web texts in more than 2,000 languages): the word
   frequencies of the archives it published per writing system (CC BY 4.0), of which its site, which
   no longer answers, left seven in the Internet Archive's Wayback Machine. Counted here, by the
   same rule.
7. An Crubadan's character trigram counts of April 2010 for 449 writing systems (GNU GPL version 3
   or later), as NLTK's data distributes them. Counted here, by the same rule but for the word
   forms, which trigrams do not show (trigram_counts says what stands for them).
8. The Universal Declaration of Human Rights, whole, in the 2012 state of the "UDHR in Unicode"
   project, as NLTK's data distributes it (its "udhr2" package, which its index calls public
   domain): a language's own file and the files named by a script. Counted here, by the same rule.
9. Google Fonts' sample texts (the same repository as 1), for a language it gives a text but no
   exemplar characters: excerpts of the same declaration. Counted here, by the same rule. An
   Crubadan and the declaration's files state no script (the one counted is taken): where Google's
   data states another for the language, it is left to this text.

A keyboard layout (evidence "k"; KEYBOARD says why it ranks between the declared and the inferred):

10. Language Tools' layouts (sven-oly/LanguageTools; Apache License 2.0), mapped by hand to a
   language and script (KEYBOARDS): the letters and marks of the script their keys and rules type
   (keyboard_reading), one layout per language and script, alone. A layout adds a language no
   source describes, or a script none gives the language in (beside Hyperglot's or a declared
   source's rows: never mixed into them); where counted sources give the language in its script,
   its row takes their place. One that types fewer than KEYBOARD_FLOOR letters and marks of its
   script, or fewer than KEYBOARD_OWN beyond an English keyboard, is refused, and so is one that
   types more than KEYBOARD_FOREIGN letters of another script (an unfinished prototype).

Reinforcement (REINFORCED_ALONE, SAME_TEXT): where two or more inferred sources describe a language
in the same script, a letter is kept when one source's rule keeps it and another source has it too
(even once, under its floor), or when it alone makes 1 letter in 500 of the source that keeps it.
A letter one crawl alone picked up (a foreign name) goes; a rare letter two texts share stays.
Measured against Hyperglot on the 220 orthographies two or more independent counted sources share
with it: a median of 7 base characters lacking (8 with the first source alone; a mean of 9.6
against 10.2), 0 beyond its base and auxiliary (0; a mean of 3.7 either way), and 28 with every
base character (25); the plain union lacks 6 but its mean beyond rises to 4.6. On the 50 that
SLDR's generated exemplars are part of: 3 lacking and 12 beyond, against 3.5 and 15 alone.
Evidence is combined only when it is independent: Google's sample text is an excerpt of the
declaration, so it adds nothing where the whole text is there, and one of An Crubadan's trigram
files that counts the declaration's own text (the cosine of their trigram counts at SAME_TEXT or
more) gives way to it. SLDR's generated exemplars give no counts: a letter of theirs is kept when
a counted source has it, or when the counted sources beside it are too short for their silence to
mean anything (SILENCE_LETTERS). The row names every source it rests on, with the letters each
counted.

Files a source filed under another language's code are read as that language (MISFILED says which,
and why).

The rule for a counted text (INFERRED_*): the text in NFC; only letters count (Unicode general
category L) and the combining marks after them; the script is the one most of its letters are in
(Scripts.txt), and letters of another script are dropped (quotations, foreign names), letters of
no script of their own (Common, as the modifier apostrophe) kept; capitals are counted with their
small letters; a character is kept when it makes at least 1 letter in 2,000 and stands in at least
3 word forms (Unilex, An Crubadan's archives), 3 different trigrams (its 2010 files), or 3 times
(a sample text); a text of fewer than 1,000 letters gives nothing.
In Latin, Greek, Cyrillic, and Armenian text a letter is counted with the combining marks on it
(Yoruba's e with a dot below and an acute); elsewhere letters and marks are counted one by one.
Digits, punctuation, and symbols never count. A counted text gives base characters only: no
auxiliary set is made up.

What each row keeps is what language_coverage.json keeps, in the same shape (so Font Check reads
both with one loader), with two more columns: its source (an index in "sources": the first it
rests on) and its evidence ("d" declared, "i" inferred, "k" a keyboard layout); an inferred row has a third, every source
it rests on with the letters that source counted ([[index, letters]], 0 where the source gives no
count). CLDR's and SLDR's exemplars list small letters only (UTS #35): each
one's capital is added (not Georgian's Mtavruli). Format characters (the zero-width joiners of some
exemplar sets) and spaces are dropped: no glyph is asked for them. The status column is "h" where
Google's data says historical, "c" where Glottolog files the language under Artificial Language,
and empty elsewhere (not given: Font Check counts such a language with the living ones). The
validity column holds SLDR's or CLDR's draft level where one is given.

The ISO 639-3 code of a BCP 47 language subtag comes from CLDR's alias table
(supplementalMetadata.xml: the three-letter code of a two-letter one, and the member languages a
macrolanguage's subtag stands for); of those, the first Glottolog has (families.py then classifies
it). A subtag any of whose codes Hyperglot has is Hyperglot's. An Crubadan's 2010 files are named
by ISO 639-3 codes: each is read as the subtag CLDR writes it with (that of its macrolanguage, where
CLDR files it under one).

It also writes checks/font_characters.json: every character the bundled list font must draw (names,
autonyms, other names, script and family headings, and the characters of every orthography and
character set), for checks/train/language_font.py. Run it once more after families.py, which reads
this script's output and gives the other names:

    python checks/train/orthographies.py --download <folder>
    python checks/train/families.py --download <glottolog folder>
    python checks/train/orthographies.py --characters

Python 3, no package needed. The sources come over HTTPS at pinned versions into the folder given
(outside the repository), each checked against its SHA-256; files already there are reused, and
Glottolog's tables are fetched by families.py's own download into --glottolog (the sibling folder
"glottolog" by default). An Crubadan's files come one at a time, a pause before each, into --texts
(the sibling folder "crubadan" by default), and Language Tools' layout files the same way into
--keyboards (the sibling folder "keyboards"); a layout is JavaScript, read as text by js_object(),
never run. The archives are read, never extracted or run; their XML is parsed by the
standard library, which is why each is pinned by its hash. The same sources give the same bytes.
"""

import argparse
import bisect
import collections
import hashlib
import io
import json
import os
import re
import sys
import tarfile
import textwrap
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ElementTree
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKS = os.path.normpath(os.path.join(HERE, os.pardir))
LANGUAGES_FILE = os.path.join(CHECKS, "language_coverage.json")
OUT_FILE = os.path.join(CHECKS, "language_orthographies.json")
LICENSE_FILE = os.path.join(CHECKS, "language_orthographies_LICENSE")
FAMILIES_FILE = os.path.join(CHECKS, "language_families.json")
SETS_FILE = os.path.join(CHECKS, "character_sets.json")
CHARACTERS_FILE = os.path.join(CHECKS, "font_characters.json")
USER_AGENT = "Mozilla/5.0 (compatible; fetch)"  # (generic: nothing of the machine or the project)

GF_TAG, CLDR_VERSION, SLDR_TAG = "0.7.9", "49", "26062.1946"
UNILEX_COMMIT = "b3a9ae27a0c29eac217bb15a75c6f8d8efb15d17"
UNICODE_VERSION = "17.0.0"
SOURCES = collections.OrderedDict((  # file name: (URL, SHA-256)
    ("lang-%s.tar.gz" % GF_TAG,
     ("https://codeload.github.com/googlefonts/lang/tar.gz/refs/tags/v%s" % GF_TAG,
      "b8d1114d0862ae47614c3081c07ef309ef02736091bd705836e4ee7845f258ae")),
    ("cldr-common-%s.zip" % CLDR_VERSION,
     ("https://unicode.org/Public/cldr/%s/cldr-common-%s.zip" % (CLDR_VERSION, CLDR_VERSION),
      "78403d8d6fb1fed6e208bf9001bf5be00bb5abfd9f8110dae062bf49309d6a89")),
    ("sldr-%s.tar.gz" % SLDR_TAG,
     ("https://codeload.github.com/silnrsi/sldr/tar.gz/refs/tags/%s" % SLDR_TAG,
      "43d64791d28df3dab330b43db62b5a16345d1ed7fca3f76120727846075b0d58")),
    ("unilex-%s.tar.gz" % UNILEX_COMMIT[:8],
     ("https://codeload.github.com/unicode-org/unilex/tar.gz/%s" % UNILEX_COMMIT,
      "2abe0b3dc86ec28d59cf3bfc6b5ce02553757e58e74e5b93671ae2225ff41e55")),
    ("unicode-%s-Scripts.txt" % UNICODE_VERSION,
     ("https://www.unicode.org/Public/%s/ucd/Scripts.txt" % UNICODE_VERSION,
      "9f5e50d3abaee7d6ce09480f325c706f485ae3240912527e651954d2d6b035bf")),
    ("unicode-license.txt",
     ("https://www.unicode.org/license.txt",
      "e7a93b009565cfce55919a381437ac4db883e9da2126fa28b91d12732bc53d96")),
    # (the three that character_sets.py pins too: general categories newer than Python's, the marks
    # scripts share, and the scripts' ISO 15924 codes, for the keyboard layouts)
    ("unicode-%s-UnicodeData.txt" % UNICODE_VERSION,
     ("https://www.unicode.org/Public/%s/ucd/UnicodeData.txt" % UNICODE_VERSION,
      "2e1efc1dcb59c575eedf5ccae60f95229f706ee6d031835247d843c11d96470c")),
    ("unicode-%s-ScriptExtensions.txt" % UNICODE_VERSION,
     ("https://www.unicode.org/Public/%s/ucd/ScriptExtensions.txt" % UNICODE_VERSION,
      "ec2107e58825a1586acee8e0911ce18260394ac8b87e535ca325f1ccbeb06bc6")),
    ("unicode-%s-PropertyValueAliases.txt" % UNICODE_VERSION,
     ("https://www.unicode.org/Public/%s/ucd/PropertyValueAliases.txt" % UNICODE_VERSION,
      "64e9a5f76f7a1e8b5a47d6a1f9a26522a251208f5276bdfa1559dac7cf2e827a")),
))
GF_ROOT, SLDR_ROOT, UNILEX_ROOT = "lang-%s" % GF_TAG, "sldr-%s" % SLDR_TAG, "unilex-%s" % UNILEX_COMMIT

# Counted texts that come one file at a time, into a folder of their own (--texts), a pause before
# each request. NLTK's data package (nltk/nltk_data) is pinned by the commit that last changed it;
# An Crubadan's own site no longer answers, so the per-language archives it published are the
# seven the Internet Archive's Wayback Machine captured, each pinned by its capture (the "id_" form of
# the address gives the bytes as they were captured).
NLTK_DATA = "https://raw.githubusercontent.com/nltk/nltk_data/%s/packages/corpora/%s.zip"
NLTK_CRUBADAN_COMMIT = "fa7aae1c5c5e26b3cc3217dae15005c471184819"
WAYBACK = "https://web.archive.org/web/%sid_/http://crubadan.org/%s/%s.zip"
CRUBADAN_ARCHIVES = (  # (An Crubadan's code of the writing system, the capture, the site's folder, SHA-256)
    ("act", "20190504105015", "files", "7d2fd48335ed57ed0d4362ef6e5ac9384f5464017dd9d54093927bf1cffbc6a0"),
    ("bcl", "20170507151047", "files", "96d59d362f95cacb6b10f5249b46c6b551811928c6a1a73b15ca9adba3fb4926"),
    ("guz", "20150530011352", "dist", "3d758a7417f6e3a1ad1e87a56acea6c43587883a2d06559ac2f9fc5fea2b9e4d"),
    ("lol", "20200603203023", "files", "af07290a8d4c5857c4705e4d4ea12fce34a76c4ae3331d731933ff050b335bf0"),
    ("pt", "20191030202901", "files", "5dafb0e626037bb407e648332451b22f53976f0a7438478d30e16554a889ad89"),
    ("so", "20220124013313", "files", "c6067f8a34c3140bdc5a5c47ae3ce4d8045f80890a0e9bc0a832ef686e242810"),
    ("urh", "20210607115712", "files", "778139b6f85ee061e218d72296456521c415d7bf00654b7dc0ba9cf6b05ab0d1"),
)
CRUBADAN_TRIGRAMS = "nltk_data-%s-crubadan.zip" % NLTK_CRUBADAN_COMMIT[:8]
# The Universal Declaration of Human Rights, whole, per language: NLTK's "udhr2" package, at the commit
# that last changed it (2013-09-28). Its index entry at that commit (packages/corpora/udhr2.xml) reads
# name="Universal Declaration of Human Rights Corpus (Unicode Version)", webpage="http://unicode.org/udhr/",
# license="public domain", copyright="public domain"; the archive holds the texts and no notice of its own.
NLTK_UDHR2_COMMIT = "5d8fe95aee5ac9014f7b3924b32715ead288441c"
UDHR2 = "nltk_data-%s-udhr2.zip" % NLTK_UDHR2_COMMIT[:8]
UDHR2_INDEX = ('<package id="udhr2" name="Universal Declaration of Human Rights Corpus (Unicode Version)" '
               'webpage="http://unicode.org/udhr/" license="public domain" copyright="public domain" unzip="1" />')
TEXT_SOURCES = collections.OrderedDict(  # file name: (URL, SHA-256)
    [("crubadan-%s-%s.zip" % (code, capture), (WAYBACK % (capture, folder, code), digest))
     for code, capture, folder, digest in CRUBADAN_ARCHIVES]
    + [(CRUBADAN_TRIGRAMS, (NLTK_DATA % (NLTK_CRUBADAN_COMMIT, "crubadan"),
                            "8d64c8ff52f47a44381cad0795cf7fe3f8ff7907a1f92c09aadef8e163efdbc7")),
       (UDHR2, (NLTK_DATA % (NLTK_UDHR2_COMMIT, "udhr2"),
                "0796c314b09a930c989c6f9d93d226af9af13feccd88496e196c743dd266c7f3"))])
# Files a source filed under another language's ISO 639-3 code: the code the source gives, then the
# language its text is in. The source's label says one thing and its content another; the content is
# trusted, because it can be checked: each file was compared, trigram by trigram, with every text of
# the declaration (udhr2), whose own codes ISO 639-3's registry and Glottolog were read against.
# - "aja": An Crubadan's 2010 table calls it "Aja", and ISO 639-3's aja is Aja (South Sudan), a
#   Kresh-Aja language. The file is the declaration in Aja (Benin), ISO 639-3 ajg, a Gbe language of
#   Benin and Togo: its trigrams have a cosine of 0.99 with udhr2's ajg text (0.41 with Ewe's and
#   Fon's), and it is written with the open o and e, the African d, and eng.
# - "hna": the table calls it "Mina", and ISO 639-3's hna is Mina (Cameroon), a Chadic language. The
#   file is the declaration in Gen, ISO 639-3 gej, the Gbe language of Togo and Benin also called
#   Mina (Glottolog lists that name for it): a cosine of 0.65 with the Aja (Benin) text and 0.50 with
#   Ewe's, the nearest of all. The "UDHR in Unicode" project of the time filed its Mina text under
#   hna too, so udhr2's own hna file is the same text (a cosine of 1.00).
# - "ako": the table calls it "Akurio", a Cariban language of Suriname. The file is the declaration
#   in Waama, ISO 639-3 wwa, a Gur language of Benin: a cosine of 1.00 with udhr2's wwa text.
# Hyperglot describes Aja (Benin), Gen, and Waama, so nothing is added under either code: the three
# rows the labels gave (Aja of South Sudan, Mina of Cameroon, Akurio) were another language's letters.
# - "tos": the table calls it "Highland Totonac". The file is the declaration's Totonac text (a cosine
#   of 0.95), which the "UDHR in Unicode" project files under top, Papantla Totonac. Two sources label
#   one text two ways, and nothing here settles which variety it is: it is kept once, under the code
#   of the project that published the text, instead of giving two languages the same letters.
# Hyperglot describes Aja (Benin), Gen, and Waama, so nothing is added under either code: the three
# rows the labels gave (Aja of South Sudan, Mina of Cameroon, Akurio) were another language's letters.
# No minimum of text decides this: the three files count 32,641, 16,672, and 6,786 letters, and the
# smallest file kept counts 3,666. build() lists any other file whose nearest text is another code's.
MISFILED = {"aja": "ajg", "hna": "gej", "ako": "wwa", "tos": "top"}
MISFILED_COSINE = 0.9  # a trigram file this near to another code's text of the declaration is reported
TEXT_PAUSE = 2  # seconds before each request for one of them
CRUBADAN = "An Cr\N{LATIN SMALL LETTER U WITH ACUTE}bad\N{LATIN SMALL LETTER A WITH ACUTE}n"

# Keyboard layouts: Language Tools (languagetools-153419.appspot.com, Craig Cornelius with Translation
# Commons), whose source is github.com/sven-oly/LanguageTools (LICENSE: Apache License 2.0; each layout
# file carries its "Licensed under the Apache License, Version 2.0" header). Pinned at the head of its
# live branch, p3_version, on 2026-11-13: its static/layouts folder holds every layout of master's
# (whose last commit is of 2023-12-21) but one, James Bay Cree's under an older name, and 25 more, and
# ten files changed since. Each file comes alone from raw.githubusercontent.com (the repository is 187
# MB of fonts, none of which is used: most carry no license).
LANGUAGE_TOOLS_COMMIT = "a9386e0031b086418f402338a7428449b08166a1"
LANGUAGE_TOOLS = "https://raw.githubusercontent.com/sven-oly/LanguageTools/%s/%%s" % LANGUAGE_TOOLS_COMMIT
LANGUAGE_TOOLS_LICENSE = ("languagetools-LICENSE", "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4")
# (layout file in static/layouts, without .js; ISO 639-3 code; ISO 15924 code of the script; SHA-256).
# A layout's file name is no reliable code (gvr's file is also there as grv, Grebo's code): each is
# mapped here by hand, from its title and what it types. Where a language and script have several, the
# one that types the most letters and marks of the script is read (ties: the first). Where a declared
# source already gives a language in a script, its layouts are read for the measure only.
KEYBOARDS = (
    # Languages no other source describes.
    ("aho", "aho", "Ahom", "388019c90ccb0840c2edef245d16ecf7dd1077e1d6c33f20915db06ba3f267e4"),
    ("aho_star", "aho", "Ahom", "1b8ec54404c1e7910e0d6ae8959d6b7bcf28dd0cab5960fef4296e3b8be995a9"),
    ("aho_star2", "aho", "Ahom", "a5ab5d5d9b4857d6f2dbf605ac00c606bb6bb69aaa8b6234dbec2cb65e56d824"),
    ("ahom_star_flex", "aho", "Ahom", "7021c879aa830a26693a71d69fc0148ef2149f4e4bbffc52ace3a992488477a0"),
    ("aio", "aio", "Mymr", "7a55223817a6bb15c0fe38af043112dd05fef6154f46081f6fbfd3a181243c98"),  # Tai Aiton
    ("bfz1", "bfz", "Takr", "8e1f38fe6bb589c240b0e5b7ec6352768147f0d0100aba44a4feac3badc8872f"),  # "Mahasu-Takri test keyboard"
    ("cja", "cjm", "Cham", "10d4c38a430f473662acf0b67eba218a5283fc4956f0068cfbb76f681892cdde"),
    # (named cja, Western Cham, and titled only with the script's own word for Cham: CLDR's likely
    # subtags give Eastern Cham for the Cham script, und_Cham: cjm_Cham_VN; Western Cham is written
    # mostly in an Arabic script)
    ("com", "com", "Latn", "f898f30376e1996f77c3e5cdf2ea8b648401127309ec3f3144eb6a0e2ae2093f"),  # "Numu Tekwapu"
    ("cst", "cst", "Latn", "20fb498e435a28c9ac5b500063752e3b9e6b6bc7208b3565503417208e04ac6a"),  # Chochenyo
    ("del", "unm", "Latn", "6228025464ca0c6fffef5478c55494f6571dfedc084db5eeb6805bd1a0137747"),
    # (del is ISO 639-2's Delaware, which ISO 639-3 splits into Unami and Munsee; "Lenape QWERTY" adds
    # the e with a dieresis for the schwa, as Unami, the Lenape of Oklahoma, is spelled)
    ("gon_deva", "gno", "Deva", "0c76d9df7b2d0797213798785794114df566291d23c782ba40259fa89d22e197"),
    # (gon is the Gondi macrolanguage: CLDR's alias table gives Northern Gondi as its member Glottolog
    # has, the Gondi of Madhya Pradesh, written in Devanagari)
    ("hke1", "hke", "Latn", "a3c918caf4cada26f7ffb3d84b1e272b8320a473a16af82aff81fec3af8e5d60"),  # "Kihunde/AZERTY"
    ("ijn", "ijn", "Latn", "38e418a3dc5f5f1b97a688c75092d4c5653ee4cfb064fe3168b67c8c1661dc6f"),  # Kalabari
    ("ijn2", "ijn", "Latn", "4b4b56d14dfd00200663433251c14dd230e968c90b5af44e7a3e666f272f36b7"),
    ("lep", "lep", "Lepc", "6cfeae5441c93dba37bb08c5f2443c1d6c02cfe43b21ba53d9ea024acaaeb46a"),
    ("lep_Munsalong", "lep", "Lepc", "4fde61ae3eb79c69ba7a777e2f8d9283005dfb9580182256f53935beb41a4b2e"),
    ("lep_rong", "lep", "Lepc", "9e2791b947e3484c3eb745857a9070b2b3fe71564451f89503bfd77e0d773261"),
    ("mez", "mez", "Latn", "62d7c806e61bf0e48eef63247afc289444f55015c9a71f4ec57b919b0d45f058"),  # Menominee
    ("mez2", "mez", "Latn", "c23680739f016d3fb8e2a467c423ed60829c9ee93b70d16e3aa66baa415cd734"),
    ("mww", "mww", "Latn", "3e65e6725492fe00ff61120796f056d5db3f326126da3c584816cc912a41bb35"),
    # ("White Hmong": the English layout under another name, which types nothing of its own: under the floor)
    ("myh", "myh", "Latn", "a8ab9e587b193fea0c5ea6309a5e62587e2058f861441719e637b0174ecb979c"),  # Makah
    ("myh2", "myh", "Latn", "5278ce0c2e6330ab0b99ca87cfd7b562c9d4e96488c95b34960577f0aeef2ae6"),
    ("oji_cree", "ojs", "Cans", "04194800bc17a9f0520d98e565a002207af50bf091a7b20d87564638aa68a225"),
    ("ojicree", "ojs", "Cans", "07bf36f27e51294c08a2c0169908aaac944ece65c18c95dd89e2a6118800e178"),
    # (Oji-Cree is Severn Ojibwa. The files ojs and fort_severn_cree, both titled "Fort Severn Cree",
    # are not read: which Cree the name means, Severn Ojibwa's or Swampy Cree's, the file does not say)
    ("phk", "phk", "Mymr", "7b6b9051b53730d7b669e2a2e13332d901a9853b7c736f2a2df4e01da91aa8ba"),  # Tai Phake
    ("phkVar", "phk", "Mymr", "cbc0860c4a7e19bc1377876c6724a09503ce4c1002c33cf5a70dcf57605ceb83"),
    ("rad1", "rad", "Latn", "aeba72c8afe39c17fbcde315b7a473dc46d24d53c3f04d342e63f7bdc7236ea3"),  # Rhade
    ("sgp", "sgp", "Latn", "f90b8e36ccbea1acd4471565a67f933eb856efb78ec999df43327b28ca79286b"),
    # ("Singphon": the English layout under another name: under the floor)
    ("srb", "srb", "Sora", "848204e14f51d4103b9565993387f97f129a8236fe87ef89e1be645510a05889"),  # Sora Sompeng
    ("tyj1", "tyj", "Tayo", "844dae066aa2301b3422d4e21cf5dacae1260324526e98df49ddc3d4a9fb9c86"),
    ("tyj2", "tyj", "Tayo", "189684ac7854e6a3c68bd1c8830938ab3e9d5d644d0babb0ac4c0966139779fc"),
    # (Tai Yo, encoded in Unicode 17.0: 11 of the code points they type are unassigned there, nine
    # in the block, U+1E6DF and U+1E6F6 to U+1E6FD, and two past it, U+1E709 and U+1E70A, and dropped)
    # Second scripts of languages a source gives in another.
    ("bla", "bla", "Cans", "d9491ee297dc9384c7bf998994004428d9143c2f3a3e5d96f6dc88b2a8e68aac"),  # Blackfoot syllabics
    ("bsq", "bsq", "Bass", "ae6c9d94bbf53add3c8e2647d9d68e09b14121bf5c7ab14ea6d318105512b75c"),  # Bassa Vah
    ("bsq2", "bsq", "Bass", "7f42275d46c0391da3b5c2f76035692add2f1131c12ee3bc7d139dfd21b0e40d"),
    ("bts", "bts", "Batk", "498cd1a1f2fc5b95610196d66703c3d40e5d56db0791e542262ff2b676987489"),  # Batak Simalungun
    ("esg_masaram", "esg", "Gonm", "47473632e37b907948711135abb867034cf422037389410ae125c48a332a7150"),
    ("gon_masaram", "esg", "Gonm", "4478bf76224f6ed05a39dcf397c5014137b77502f5715e59365c84bbe075319d"),
    # (CLDR's likely subtags give Aheri Gondi for Masaram Gondi: und_Gonm: esg_Gonm_IN)
    ("ff_adlam", "fuf", "Adlm", "894702b20ed4329ffc128daeb704e1f0d264bd373a4ae47adc4d0efc306d3705"),
    # (titled "Pular/Fulfulde" in Adlam; ff is the Fulah macrolanguage, and CLDR's likely region for
    # it in Adlam is Guinea, whose Fulah is Pular: und_Adlm: ff_Adlm_GN)
    ("gon_gunjala", "wsg", "Gong", "fa7cd7c171dd1dced4749a76d1304f93aee34fc265c8d0be4ddaea8e8044d67c"),
    # (CLDR's likely subtags give Adilabad Gondi for Gunjala Gondi: und_Gong: wsg_Gong_IN)
    ("gon_telu", "wsg", "Telu", "2e9011e89cc70316eba1ab2fb1e1a847bfd6b7e64928aadaf855b59f4663fc0a"),
    # (Gondi in Telugu letters is the Gondi of Telangana, Adilabad Gondi, the language SLDR files its
    # Telugu orthography under. Refused as unfinished, KEYBOARD_FOREIGN says why: its shift layer
    # types Tibetan, and SLDR's generated exemplars stay)
    ("gvr", "gvr", "Gukh", "ee446962c09efa01f53460a0076764a1418585915714cb30c0e109981e5752d0"),
    # (Gurung Khema, encoded in Unicode 16.0; und_Gukh: gvr_Gukh_NP. The same file is there as grv)
    ("hoc", "hoc", "Wara", "b1b80fbc90ef1be6b13dede6ec94b52eacb8b82b70432eaccd96ba042c31c5ec"),  # Ho in Warang Citi
    ("ku_Yezi", "kmr", "Yezi", "09c60ec224c45a89219655a99bfc06c42b75e5fdad665f9764631d92219a7abf"),
    # (ku is Kurdish; the Yezidi script's language, und_Yezi: ku_Yezi_GE, is the Kurmanji of the
    # Yazidis of Georgia and Armenia, Northern Kurdish)
    ("lzz_Latn", "lzz", "Latn", "7c150501e4ea69432882e6e93f0722f72929610d3597e900b8a005e361a6e501"),  # Laz in Turkey
    ("mni2015", "mni", "Mtei", "c1d8d3d5671ad0b6c464889a03738436f6ba87bea7d20d225477fee415b29740"),
    ("mniCdac", "mni", "Mtei", "d1c84929457670c96b3b1220dbaae97d049fd8f651f6aef4a7cb89a485aa2314"),
    ("mniMtei", "mni", "Mtei", "57b28e3cb9edfffd7ecb653adada9af82268f48fab4ef660c11f88d7d7965fe0"),
    ("mniMtei_extensions", "mni", "Mtei", "000f64648e55290e3c4f517ff027279ce35e43f29646bced6665e701689648f0"),
    ("mni_kanglei", "mni", "Mtei", "aab0d409baf80c3dbcac4bda4d0fa7169fe422e6decd5e482d17170daba8a691"),
    ("mni_leimaren", "mni", "Mtei", "cf499850edef6cc7f7edc9eb342048b6ca05683f74aabb7a16637780188f66f0"),
    ("nnp", "nnp", "Wcho", "ba3ffc34955bd0eb83bd54ac0a01431d32d8aedaede85e7388c5668c3b05fa90"),  # Wancho
    ("tmh", "ttq", "Tfng", "aa1e487e21ef0c687ca6b958aeb7f7f0941489b2fe673d946e1cacef41700aca"),
    # ("Tamashek": tmh is the Tamashek macrolanguage, for which CLDR's alias table gives Tawallammat
    # Tamajaq; the layout follows CLDR's keyboard chart for tmh)
    ("xmf_Latn", "xmf", "Latn", "6170f28eb77e084dde0aa70cd845da96814537d7d48c405b5bfde0228c8905f8"),  # Mingrelian
    ("xmf_Latn2", "xmf", "Latn", "b1ebdb758f7251c48a9289b317f08b600c41739de6c3dc40ea722069e946ef30"),
    # Languages inferred from a text in the same script: the layout's row takes the place of the
    # counted one, ranked before it (KEYBOARD below says why).
    ("crk_phonetic", "crk", "Cans", "a659e7be538ec282b8dd44a668f6e6a8968fb189f58bbd0068a8720841749eb6"),  # Plains Cree
    ("cto", "cto", "Latn", "d90e6c315e23f00114fa085d457ecd409ef05ef60e4808b2cb15bbc9f1494b8b"),  # Embera Catio
    ("cto_102", "cto", "Latn", "0816f22a584f48c9ea48bd42715c928f7ef1665d07938897eab03697e4d1bfa6"),
    ("cto_hybrid", "cto", "Latn", "d205f35229212f0d1b1486ec8755881118af247b4700bc6aabb41632a80cf702"),
    ("cto_hybrid_freq", "cto", "Latn", "e87706f43f047076f02d2f50a97243a12ad816249d9f95fee5777eb52808aef9"),
    ("kht", "kht", "Mymr", "e52b0f8800310164505c3eaa39fae01e572941a4c6841bc5e5cfbc43cc9f4d7e"),  # Khamti
    ("ksw", "ksw", "Mymr", "5f6db834d1bcfd50ebaf0452f408481fc7d3b831f53b792d78cfb5618053e209"),  # S'gaw Karen
    ("lut", "lut", "Latn", "4837778b151c3834defb5c16d9001d0e2a48ce1b05fd92b09f33d465c1476ab4"),  # Lushootseed
    ("mro", "mro", "Mroo", "a00220a28e3390c75df94fc6dfd3d19ad9f00cb7182158a60046a25bb5aa3798"),
    # (Not read: Sylheti's two Syloti Nagri layouts, syl and syl2, which have no key for kho (U+A808),
    # cho (U+A80D), or the anusvara (U+A80B): the row SLDR's generated exemplars and Google's sample
    # text make has them, and is the better one)
    ("unrUnicode", "unr", "Nagm", "d49f8f700f778dc3dd8e777f5ebe54a03f53f4b061346c35f052195b40bb0d7d"),  # "Mundari Bani"
    # Languages a declared source gives in the same script: read for the measure only.
    ("cho", "cho", "Latn", "b69521d3737410ef4f386d4e94653398193bd54d1ebc0dd228735686949e3e23"),
    ("cho2", "cho", "Latn", "4972aef0b044681c5f427ec38bef5006e31104be76e8fd040d9e1bd69339ba63"),
    ("hnj", "hnj", "Hmnp", "ce520006a435acb691b814b355ff18ce28a2846c4953aa4feaad4ea2551d3828"),
    ("mor", "mor", "Latn", "841f921ad15c46fbeaeecb2d3bebd10d0bd34da378f44f80a87c105978d5153b"),
    ("nstUnicode", "nst", "Tnsa", "6bd6af794ca86cdb7d17b9d23287434b79e6b6d7063032e30b91f45d5be07298"),
    ("one", "one", "Latn", "b9e530f844d8c64e96d7855c7e048a54757067fd2f48f9d4563d0855cde4ea1e"),
    ("one2", "one", "Latn", "779406456aadc949b98b4abad2e34163c30bed024c7f04b2a67820edf4476f4c"),
    ("one3", "one", "Latn", "e3fadd65bb926b94425269aa4b1266616c4ff968b3c7487f48d86beb067a3fb3"),
    ("one4", "one", "Latn", "2fe536b45766017b34ea224d394b5d985f790035ae5dc304c00cba5a2719ec8f"),
    ("onemobile", "one", "Latn", "b6a9ba9f0e1adbec18760a4a16047e0af31200af478d6b01fe086a4573479557"),
    ("ovd", "ovd", "Latn", "110966b5886b5b80a07d3042bd854ced9129fe370b771f7b637a838874b4cf8f"),
    ("pcm", "pcm", "Latn", "07e4d133a87e115018d3680d1c0ed53d17098ea3b01616593d3a05cdc0beaaf3"),
    ("rhg", "rhg", "Rohg", "9d52208cd9780c4ad26a101e37e9f77c66e18223a6f7c76d4727e9745b5d3654"),
    ("rhg2", "rhg", "Rohg", "0385d1b9ddd60a657b4611836f8857af7fc51c97b7bde5ccd1886ad3926208c3"),
    ("rhg3", "rhg", "Rohg", "3997e97cef1bb73ece377d39d6a251a675bbf80a3f90ecb8d85ae341a061d413"),
    ("rhg_arab", "rhg", "Arab", "ab47b72bb7b3ef5a361d512b57c66524e05afb52396f269e271ca02c6c5b3143"),
    ("sat", "sat", "Olck", "38fd7ec27d5924008185a9ae3ee23cab29c5ad5878a057549a8a36a1ccb031fa"),
    ("sat2", "sat", "Olck", "26dba01960d227785b0ef3ed654f4e48cc26a5cdd8ae9b56e0efef467887ca73"),
    ("sat3", "sat", "Olck", "a478c72aa1f03b1ab8d0fccb6074c105542aa214ff0477471c19193d2de6cbce"),
    ("satOFDN", "sat", "Olck", "b7ef6c1476dc9183255a84b8ffa9454bb48086a51e04a3562e109e7c8d460ede"),
    ("suz_unicode", "suz", "Sunu", "afa849b7ecc99624e971dd1d9d26ad098e8c04232ecb21dbb7b83772d50d6d86"),
    # Languages Hyperglot gives in the same script: read for the measure only. Not read: yo1983 (the
    # Yoruba orthography proposed in 1983) and fr (Swiss French): another orthography's or country's.
    ("ar", "arb", "Arab", "b735377774c65842171df1b840fd659b9acb16871d96247896c1ba10b24a6182"),
    ("as1", "asm", "Beng", "f15db38e04e086d9ac6c6f757298a846802a2373924e59b9dff7d900f9638405"),
    ("as2", "asm", "Beng", "adfc4f3992b23eec03c83605cdd73d281ca80c63af84b5d750f0a62199be87d8"),
    ("as_indic3", "asm", "Beng", "4d804b46eeddc0834ad4d7a2434d33b9349b739ec22cd1e06bae45923fcefeb3"),
    ("bax", "bax", "Bamu", "d9fcb11de14eb0b3d69ffa399f7f88050eb1d1967f3bc36a959c83934a7cf2c2"),
    ("blt", "blt", "Tavt", "57552af15f695ab48fb7cbc23eaa12fcf2fe10deb0cbce0068ba7156e02d6116"),
    ("bn_b2", "ben", "Beng", "f65810a733c561814edf1c3c34ca68c5f55b1c436c6898179db22e0f2fb93634"),
    ("bn_b3", "ben", "Beng", "5bb940d82c9c03434c431927cba8264cf5fc0b2d185f3ddf12afff8cf7a95c50"),
    ("bo", "bod", "Tibt", "eb285ef90270b08a98d50329a70a8dd8f382c7e6ad80be01542ac6433813fc5d"),
    ("bod", "bod", "Tibt", "dfbc7083f0a0fcd51930d7d267a702a4af866687a38cb4c2e12e7677e7df2e3b"),
    ("bod_wylie", "bod", "Tibt", "d7f11ea93b712f5f974d3e21089329be55078abe26a751356218485b947b472e"),  # (also as bo_wylie)
    ("ccp", "ccp", "Cakm", "f62d5e4fda6c3ce9bbed55fd6411d1a6286ac689db5a4556473b3ae1ddc881a5"),
    ("ccp_reorder", "ccp", "Cakm", "abf466dec132827ef7c573f3a7968c582abb03a590885050e8e674d666f7ed57"),
    ("chr", "chr", "Cher", "da200c0841991c0840c9f0ecb70ca1f4a43151b4bcbeb2db3e6f4ec1bb0b88f5"),
    ("chr_phone", "chr", "Cher", "7a4763e8fc4b8907a0867425944e082fcf422a0c3a683d4962c45a7fe67e4ac6"),
    ("ckb_ar1", "ckb", "Arab", "bc8123b329fc4620b6f486282b1d31ad9901e622dfc38338af0d60866be2d40c"),
    ("ckb_en1", "ckb", "Arab", "dd33a3508e96890873db183aa96ea7b69ea182b560dc6dcb1ff8d650692a7797"),
    ("fr_1", "fra", "Latn", "405ada093ddfa9e0846fe9473195a2df7b1ef3faf5f49b6e3b50fd7509afce1f"),
    ("iu_nunavut", "ike", "Cans", "f5d54494a623e980e230602a68e9962ab80080127cc738634abbcfd17a6ff59e"),
    # (iu is Inuktitut, for which CLDR's alias table gives Eastern Canadian Inuktitut, Nunavut's)
    ("kgp1", "kgp", "Latn", "f69c9ad3cf7ce57885da6d7389fe3202e436793b46794c61472f5a1653ac204d"),
    ("kyu", "kyu", "Kali", "cca51ff283e0a5a867f6c42137729f5f9bfbde8583bbb09d39c9271dd1085701"),
    ("lkt_plain", "lkt", "Latn", "ea8271303263908921180ac6b6d6914ea2dc7c8879448f5e5f2429ed9b7956c6"),
    ("mnw", "mnw", "Mymr", "7d3eb3e5a513eb733a9e460823662a69d94432d418dc7a65412d84c3c9d4697c"),
    ("mnw_mul", "mnw", "Mymr", "2ee3128620dcd97aa44366f4252a39cddc5aac29d5b49bdad1d5981f73336116"),
    ("my", "mya", "Mymr", "166ca1cd43b1c49e835f4037dea69e9f50491491cdd742d21f324691fbc2a041"),
    ("nv", "nav", "Latn", "9a4d281085e6c660520ac4696a3739bc6d4ddc691ce62460eea65108d80a7042"),
    ("nv_std", "nav", "Latn", "61ebc1d35725f2f456902279e38078d3b33619e4874ca052ce0c644b7c3bca53"),
    ("shn", "shn", "Mymr", "783c47a3e4a5ff8c236e33ef8ad4e8311f3f992df7429cdcbe54d3b31f913488"),
    ("shn_keyman", "shn", "Mymr", "0cc285a44762a8773689a23a59ddb36b6e29e6831c16b079847e58535304400e"),
    ("shn_sil_keyman", "shn", "Mymr", "37b270800f9119b8f653b0c6d7cfc463f8c8e4027ebf8b38ea474848fb59562d"),
    ("so1", "som", "Latn", "d1800c26e6a8e08516414237241747b2e4849f9c6ace8c722a6747ee41111365"),
    ("so2", "som", "Latn", "5e126748aed15f2aab4bbc04dc47679096e6c46b10c512eecb3acc0452564033"),
    ("sol2", "som", "Latn", "5e6c88bd472ee70a2c64400676bb722be34397cdc69fd06388c6b067f80d1216"),
    ("ta_phonemic_a", "tam", "Taml", "f633bf68a94bc32c134cc841e362e775a181dccd42037a6a3ffb49cb635bb506"),
    ("to", "ton", "Latn", "5840409ea0f8cd984587e6d613c0bbc96b11009e4b202b1ea3d2cfdc02e5a28b"),
    ("to_nom", "ton", "Latn", "6fe9ad1540d8422b3da9fa534b5f4a491a773c2025bbf4fe0a69c8bec9e52a86"),
    ("win2", "win", "Latn", "023f7380b32856e2cd693b381626434e5d0e1be3620d2a880d571f4a93ac7b50"),
    ("win_latn", "win", "Latn", "fce0de77ec63f0e5c42fb25e9f03bec0e2afa99745b5a42f9a3c2848f16d09fa"),
    ("xmf", "xmf", "Geor", "20491a5ab80c2d74a727c64d2c79481a26e7389a48639f7eff81d7a2c6d940d3"),
    ("yo", "yor", "Latn", "4064d8aae67748c878a002966a1101d3633f47610fe7034ae89eba6bfd2f559e"),
    # Layouts named for a script they do not type, read to show the floor refuses them: Mende Kikakui's
    # three (men types Bassa Vah; the others, private-use code points), Tulu's (tcy types Malayalam, not
    # Tulu-Tigalari), Wolof's in Garay (Latin), and Zaghawa's in Beria Erfe (Latin and private use).
    ("men", "men", "Mend", "863ddd1da70b3b7fd1f53d582ccdcacca901f2dec103a65e4fd5c37beb1656d7"),
    ("men2", "men", "Mend", "1eb1669de8b3cc77b468708ec8424a3e103f87f7a48a4c64f4fb2abaddacdfd1"),
    ("menphone3_unicode", "men", "Mend", "ceb88e0893fca4d5d883210fef4b1a26db627d26ebf626305e852e106601017d"),
    ("tcy", "tcy", "Tutg", "16b439776487d6cbd7bd2db709283cfc4af5aa9b67125df29baebe8a6809ca2e"),
    ("wo_Gara", "wol", "Gara", "e45e83847ecefa11c09b235eabdf38683667925358d37188ffc8d3550c6ec5af"),
    ("zag", "zag", "Berf", "2f6ac34522b7361fedbe89b45f675b46f389cef0fd216256e6798f470ba45da5"),
    # Not mapped: the layouts of scripts Unicode has not encoded, which type private-use or unassigned
    # code points (Bete, Kpelle, Loma, Qiang's Rma, Kurmali's Chisoi, Lampung, Wolof's Catya, Igbo's
    # Nsibidi), Kaktovik numerals (digits), a language family's ("omq": Oto-Manguean), English and
    # emoji layouts, legacy-font encodings in Latin letters (Mundari's, Sunuwar's Mukdum, Kurmali's
    # kyw1), Vietnamese in a proposed new spelling, Irish (a stub titled "title") and Irish in Ogham (no
    # orthography of a language here is written in Ogham), "Cree Central 1" and "James Bay Cree" (which
    # Cree is not said), "Anangu Yolngu" (two languages named), and lkt_plain_pua (private use).
)
# The floor, from the data: the layouts named for a script they do not type give 0 of its characters,
# and the English layouts under other names give nothing beyond a to z; the fewest of a layout kept
# are 25 letters and marks outside Latin (Batak and Sora Sompeng) and 2 beyond a to z in Latin
# (Menominee's first layout). Between them falls only a five-letter Assamese prototype (as_indic3).
KEYBOARD_FLOOR = 20  # letters and marks of the script a layout must type (in Latin, a to z and their capitals count) ...
KEYBOARD_OWN = 2  # ... of which at least this many an English keyboard does not type (outside Latin: all of them)
# A layout whose layers (but the Latin fallback keyboard_reading skips) or rules type letters of a
# script other than its own, Latin, and Common or Inherited is a prototype copied from another
# script's layout and not finished: gon_telu's shift layer types Tibetan (6 letters, with Tibetan
# vowel signs), its caps-lock layers plain Latin, its transform one placeholder rule, and its row
# lacked 5 independent vowels and 8 of the 11 marks of the counted row it replaced. Only letters
# count (general category L), a small letter and its capital once. Finished layouts type a stray
# one or two, so a few are let through: the three Ahom star layouts a Sogdian mem (U+10F3A, beside
# 48 Ahom letters and marks; refused, they would leave Ahom to a layout typing 8 fewer), a Catio one
# a Hangul vowel (U+1181), Sunuwar's a Greek omega (the ohm sign), and Ho-Chunk's win_latn a theta
# and a chi on its Control layers. Of the 131 layouts read, none but gon_telu (6) and the two the
# floor already refuses (men: 28 Bassa Vah letters; tcy: 33 Malayalam) types more than 2.
KEYBOARD_FOREIGN = 2  # letters of another script a layout may type (more: refused as unfinished)
KEYBOARD_PAUSE = 1  # seconds before each request for one of them
KEYBOARD_SOURCES = collections.OrderedDict(  # file name: (URL, SHA-256)
    [(LANGUAGE_TOOLS_LICENSE[0], (LANGUAGE_TOOLS % "LICENSE", LANGUAGE_TOOLS_LICENSE[1]))]
    + [("%s.js" % name, (LANGUAGE_TOOLS % ("static/layouts/%s.js" % name), digest))
       for name, _, _, digest in KEYBOARDS])

# The sources a row may name, in the order of preference; a row's source column is an index here.
# [key, what a tooltip says, license]
SOURCE_ROWS = (
    ("gflanguages", "Google Fonts' language data (gflanguages %s)" % GF_TAG, "Apache License 2.0"),
    ("cldr", "Unicode CLDR %s" % CLDR_VERSION, "Unicode License V3"),
    ("sldr", "SIL's Locale Data Repository (SLDR %s)" % SLDR_TAG, "MIT License"),
    ("keyboard", "Language Tools (sven-oly/LanguageTools, commit %s)" % LANGUAGE_TOOLS_COMMIT[:8], "Apache License 2.0"),
    ("sldr-generated", "SIL's Locale Data Repository (SLDR %s), generated by SIL's tools" % SLDR_TAG, "MIT License"),
    ("unilex", "Unilex word frequencies (Unicode, commit %s)" % UNILEX_COMMIT[:8], "Unicode License V3"),
    ("crubadan", "%s's word frequencies (Kevin Scannell)" % CRUBADAN, "CC BY 4.0"),
    ("crubadan-trigrams", "%s's character trigrams of 2010 (Kevin Scannell, in NLTK's data)" % CRUBADAN,
     "GNU General Public License, version 3 or later"),
    ("udhr2", "The Universal Declaration of Human Rights, whole (NLTK's udhr2 package)", "public domain"),
    ("gflanguages-text", "Google Fonts' sample text (gflanguages %s)" % GF_TAG, "Apache License 2.0"),
)
# The inferred sources, the best measured first (docs/FONT-CHECK.md has the table): on the 166
# orthographies Hyperglot shares with both, the declaration's whole text lacks a median of 9 base
# characters and An Crubadan's trigrams 8, so it comes after them, and far before the excerpts.
INFERRED = ("sldr-generated", "unilex", "crubadan", "crubadan-trigrams", "udhr2", "gflanguages-text")
# A keyboard layout is evidence of a third kind ("k"): neither an orthography a maintained source
# declares nor a text counted, but a keyboard author's statement of the characters a language's
# writers type. It ranks after every declared source and before every inferred one: measured against
# Hyperglot on the 23 languages and scripts both have, a layout lacks a median of 2 base characters
# (mean 11.5: phonetic layouts that compose letters by rules, and prototypes, lack many) and has 3
# beyond its base and auxiliary ones, against 3 and 10 for SLDR's generated exemplars, the best of the
# inferred; on the 18 that a counted source has too, the layout lacks 1.5 against 11.5 for the row
# the counted sources make, and has 2 beyond against 0. It is never a second witness: added to the
# counted sources by REINFORCED's rule, it takes the lacking from 11.5 to 3 but the beyond from 0 to
# 0.5 (a mean of 2.2 to 3.8), and against the layout alone the lacking rises from 1.5 to 3; the rule
# asks of a second source that it lower the one without raising the other. So a layout's row rests on the layout alone, and takes the place of a counted
# row of the same language and script. Never mixed into a declared row: it adds a language no source
# describes, or a script none gives the language in.
# No count of the counted row's letters a layout lacks is asked of it before it takes the row's place,
# because none tells a worse layout from a better one. Of the seven rows layouts replace, Plains
# Cree's lacks the most (24 of 110 letters, against 75 added: the eastern finals, Th-Cree's and
# Sayisi's letters, and the w-dots of other Cree that the crawl mixed in), and it is the best of them;
# Catio's lacks 10 vowels with an acute or a tilde that its rules type as a mark after the vowel (it
# has the marks); the rest lack 0 to 6 letters and marks, against 7 to 17 added. Sylheti's layouts
# (5 lacking, 1 added) were the one clearly worse, and are taken out of KEYBOARDS by hand.
# Lushootseed's lacks the c, s, and x with a caron (a dead caron key its stub transform gives no
# rule), and its counted row the l with a stroke, p, and q: neither is the better.
KEYBOARD = "keyboard"
# What a source's count is a count of, for a tooltip to say how much text a row rests on: the letters
# of a text, those of a list's distinct word forms, or nothing (SLDR gives exemplars, no count).
COUNTED_AS = {"unilex": "words", "crubadan": "words", "crubadan-trigrams": "text", "udhr2": "text",
              "gflanguages-text": "text"}

INFERRED_SHARE = 1 / 2000.0  # a character kept makes at least this share of the letters counted
INFERRED_TIMES = 3  # ... and stands in at least this many word forms (or times, in a sample text)
INFERRED_LETTERS = 1000  # a text of fewer letters gives nothing
REINFORCED_ALONE = 4  # with several sources, a letter only one has is kept at this many times the share (1 in 500)
SILENCE_LETTERS = 5000  # the letters counted from which a letter's absence takes it from a source without counts
SAME_TEXT = 0.8  # the cosine of two texts' trigram counts from which they are one text counted twice
UDHR_SCRIPTS = ("Arab", "Cyrl", "Hans", "Hant", "Latn", "Mong", "Tfng", "Tglg")  # the scripts udhr2's files are named by
CLUSTERED_SCRIPTS = ("Latin", "Greek", "Cyrillic", "Armenian")  # a letter counted with the marks on it
MARK_BASE = "\N{DOTTED CIRCLE}"
ARTIFICIAL = "arti1236"  # Glottolog's family of constructed languages
SLDR_NS = "{urn://www.sil.org/ldml/0.1}"
SLDR_DEFAULT_DRAFT = "proposed"  # SLDR's manual: an element without a draft level, in a file without one
SLDR_LEFT_OUT = ("suspect",)  # "for retaining data that is considered wrong"
INHERITED = "\N{UPWARDS ARROW}\N{UPWARDS ARROW}\N{UPWARDS ARROW}"  # CLDR: the value of the parent locale

# ISO 15924 code: the script's name. Hyperglot's own name where Hyperglot has the script (one section
# per script in the list); Google's name otherwise (its scripts/*.textproto), read from the archive.
SCRIPT_NAMES = {
    "Aran": "Arabic", "Beng": "Bengali", "Cans": "Canadian Syllabics", "Egyp": "Egyptian Hieroglyphs",
    "Ethi": "Ge\N{MODIFIER LETTER REVERSED COMMA}ez", "Geok": "Georgian", "Hang": "Hangul", "Hani": "Chinese",
    "Hans": "Chinese", "Hant": "Chinese", "Kore": "Hangul", "Lana": "Tham", "Lisu": "Lisu", "Mymr": "Burmese",
    "Orya": "Oriya", "Sarb": "Ancient South Arabian", "Xsux": "Sumero-Akkadian Cuneiforms", "Yiii": "Modern Yi",
}
# Unicode's script names (Scripts.txt) that differ from the names above, for a counted text.
UNICODE_SCRIPTS = {"Bengali": "Beng", "Canadian_Aboriginal": "Cans", "Ethiopic": "Ethi", "Han": "Hani",
                   "Myanmar": "Mymr", "Oriya": "Orya", "Tai_Tham": "Lana", "Yi": "Yiii", "Nko": "Nkoo",
                   "Old_South_Arabian": "Sarb", "Cuneiform": "Xsux", "Egyptian_Hieroglyphs": "Egyp", "Hangul": "Hang",
                   "Miao": "Plrd"}  # (Unicode's Miao is the Pollard script)


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(folder, sources=None, pause=0):
    """{file name: local path} of the pinned sources (SOURCES, or those given), fetched when not
    there yet (after a pause of so many seconds, when one is asked for), each checked."""
    os.makedirs(folder, exist_ok=True)
    found = {}
    for name, (url, digest) in (SOURCES if sources is None else sources).items():
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            time.sleep(pause)
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=300) as response, open(path + ".part", "wb") as handle:
                for block in iter(lambda: response.read(1 << 20), b""):
                    handle.write(block)
            os.replace(path + ".part", path)
        if sha256_of(path) != digest:
            raise SystemExit("%s: SHA-256 %s, expected %s" % (path, sha256_of(path), digest))
        found[name] = path
    return found


# ---------------------------------------------------------------------------
# Characters: the shape language_coverage.json keeps (as checks/train/languages.py makes it)
# ---------------------------------------------------------------------------

# Code point: general category, where the pinned UnicodeData.txt says another than Python's own data
# (which is older: Python 3.14 has Unicode 16.0, so Tai Yo's letters, encoded in 17.0, were unassigned
# to it and dropped). Filled by pinned_categories(); empty, Python's data alone is read.
CATEGORIES = {}


def category(ch):
    return CATEGORIES.get(ord(ch)) or unicodedata.category(ch)


def pinned_categories(path):
    """Fill CATEGORIES from UnicodeData.txt (its ranges, written as First and Last, included)."""
    CATEGORIES.clear()
    first = None
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            fields = line.split(";")
            if len(fields) < 3:
                continue
            code, name, kind = int(fields[0], 16), fields[1], fields[2]
            if name.endswith(", First>"):
                first = code
                continue
            for one in range(first if first is not None and name.endswith(", Last>") else code, code + 1):
                if unicodedata.category(chr(one)) != kind:
                    CATEGORIES[one] = kind
            first = None


def is_mark(ch):
    return category(ch).startswith("M")


def dropped(ch):
    """Format characters, controls, and spaces: no glyph is asked for them."""
    return category(ch) in ("Cf", "Cc", "Zs", "Zl", "Zp", "Cs", "Co", "Cn")


def clusters_of(text):
    """The NFC clusters of a text: each a character, or a letter and the combining marks Unicode has
    no single character for; a lone mark stays alone. The dotted circle marks are shown on is taken off."""
    text = unicodedata.normalize("NFC", "".join(ch for ch in text.replace(MARK_BASE, "") if not dropped(ch)))
    found, current = [], ""
    for ch in text:
        if current and is_mark(ch) and not is_mark(current[0]):
            current += ch
        else:
            if current:
                found.append(current)
            current = ch
    if current:
        found.append(current)
    return found


def items_of(elements):
    """The characters of a list of elements (a character, or a string: a digraph is split into its
    letters, which Hyperglot does not check as units either), each once, in order."""
    found = []
    for element in elements:
        for cluster in clusters_of(element):
            if cluster not in found:
                found.append(cluster)
    return found


def decomposed_marks(items):
    marks = set()
    for item in items:
        marks.update(ch for ch in unicodedata.normalize("NFD", item) if is_mark(ch))
    return marks


def required_marks(listed, base, auxiliary):
    """The marks an orthography needs on their own, as languages.py keeps Hyperglot's: the listed
    marks no base or auxiliary character decomposes into, and the marks of base clusters Unicode has
    no single character for."""
    derived = decomposed_marks(base) | decomposed_marks(auxiliary)
    found = [ch for ch in listed if ch not in derived]
    for item in base:
        if len(item) > 1:
            found += [ch for ch in item[1:] if is_mark(ch)]
    return "".join(sorted(set(found), key=found.index))


def split_marks(items):
    """(the characters that are no lone marks, the lone marks)."""
    return ([item for item in items if not all(is_mark(ch) for ch in item)],
            [ch for item in items if all(is_mark(ch) for ch in item) for ch in item])


def capital_of(item):
    """The capital of a small letter (or of a letter and its marks), or None: no capital, one of
    several characters (a sharp s), or Georgian's Mtavruli, which no ordinary text needs."""
    upper = unicodedata.normalize("NFC", item.upper())
    if upper == item or len(clusters_of(upper)) != 1 or len(upper) != len(item):
        return None
    if 0x1C90 <= ord(upper[0]) <= 0x1CBF:
        return None
    return upper


def with_capitals(items):
    found = []
    for item in items:
        for one in (item, capital_of(item)):
            if one and one not in found:
                found.append(one)
    return found


class Orthography(object):
    def __init__(self, tag, script, name, autonym, base, auxiliary, marks, source, validity="", speakers=0,
                 historical=False):
        self.tag, self.script, self.name, self.autonym = tag, script, name, autonym
        self.base, self.auxiliary, self.marks = base, auxiliary, marks
        self.source, self.validity, self.speakers, self.historical = source, validity, speakers, historical
        self.rests = None  # an inferred one: [(source, the letters it counted)], every source it rests on


def shaped(tag, script, name, autonym, base, auxiliary, listed_marks, source, capitals, **more):
    """An Orthography from a source's lists of characters, or None when it has no base character.
    Lone marks in the base list are marks the orthography needs; in the auxiliary list they are left
    out (Hyperglot's auxiliary characters hold none either)."""
    base, base_marks = split_marks(items_of(base))
    auxiliary, _ = split_marks(items_of(auxiliary))
    if capitals:
        base, auxiliary = with_capitals(base), with_capitals(auxiliary)
    auxiliary = [item for item in auxiliary if item not in base]
    if not base:
        return None
    listed = base_marks + [ch for item in items_of(listed_marks) for ch in item if is_mark(ch)]
    return Orthography(tag, script, name, autonym, base, auxiliary, required_marks(listed, base, auxiliary), source,
                       **more)


# ---------------------------------------------------------------------------
# CLDR: codes, likely scripts, English names, exemplars
# ---------------------------------------------------------------------------

class UnsupportedSet(ValueError):
    pass


def parse_set(text):
    """The elements of a UnicodeSet as exemplar characters are written ([a b {ch} d-f \\u0301]):
    characters, ranges, strings in braces, and backslash escapes. A set with properties or nested
    sets raises UnsupportedSet: no exemplar read here has one."""
    text = text.strip()
    if not (text.startswith("[") and text.endswith("]")):
        raise UnsupportedSet(text[:40])
    text, at, found, ranging = text[1:-1], 0, [], False

    def escape(at):
        ch = text[at]
        if ch == "u":
            return chr(int(text[at + 1:at + 5], 16)), at + 5
        if ch == "U":
            return chr(int(text[at + 1:at + 9], 16)), at + 9
        if ch == "x":
            return chr(int(text[at + 1:at + 3], 16)), at + 3
        if ch == "N":
            end = text.index("}", at)
            return unicodedata.lookup(text[at + 2:end]), end + 1
        if ch in "pP":
            raise UnsupportedSet("property")
        return ch, at + 1

    def add(element):
        nonlocal ranging
        if ranging:
            low = found.pop()
            if len(low) != 1 or len(element) != 1 or not 0 < ord(element) - ord(low) < 20000:
                raise UnsupportedSet("range %r-%r" % (low, element))
            found.extend(chr(code) for code in range(ord(low), ord(element) + 1))
            ranging = False
        else:
            found.append(element)

    while at < len(text):
        ch = text[at]
        if ch.isspace():
            at += 1
        elif ch == "\\":
            element, at = escape(at + 1)
            add(element)
        elif ch == "{":
            at += 1
            string = ""
            while text[at] != "}":
                if text[at] == "\\":
                    element, at = escape(at + 1)
                    string += element
                elif text[at].isspace():
                    at += 1
                else:
                    string += text[at]
                    at += 1
            at += 1
            add(string)
        elif ch == "-" and found and at + 1 < len(text):
            ranging, at = True, at + 1
        elif ch in "[]&":
            raise UnsupportedSet("nested set")
        else:
            add(ch)
            at += 1
    return found


class Codes(object):
    """CLDR's tables: the ISO 639-3 codes a language subtag stands for, its likely script, and its
    English name."""

    def __init__(self, archive):
        self.overlong, self.members = {}, collections.defaultdict(list)
        root = ElementTree.fromstring(archive.read("common/supplemental/supplementalMetadata.xml"))
        for alias in root.iter("languageAlias"):
            code, tag, reason = alias.get("type"), alias.get("replacement"), alias.get("reason")
            if reason == "overlong" and len(code) == 3 and len(tag) == 2:
                self.overlong[tag] = code
            elif reason == "macrolanguage":
                self.members[tag].append(code)
        self.short = dict((code, tag) for tag, code in self.overlong.items())
        self.macro = dict((self.overlong.get(code, code), tag) for tag in sorted(self.members)
                          for code in self.members[tag])
        self.likely = {}
        root = ElementTree.fromstring(archive.read("common/supplemental/likelySubtags.xml"))
        for one in root.iter("likelySubtag"):
            parts = one.get("to").split("_")
            if len(parts) > 1 and "_" not in one.get("from"):
                self.likely[one.get("from")] = parts[1]
        self.names = {}
        root = ElementTree.fromstring(archive.read("common/main/en.xml"))
        for one in root.iter("language"):
            if one.get("type") and one.text and one.get("alt") is None:
                self.names[one.get("type")] = one.text

    def isos(self, tag):
        """The ISO 639-3 codes a language subtag may stand for: its own (the three-letter code of a
        two-letter subtag), then the member languages a macrolanguage's subtag is used for."""
        found = [self.overlong[tag]] if tag in self.overlong else [tag] if len(tag) == 3 else []
        for code in self.members.get(tag, ()):
            code = self.overlong.get(code, code)
            if len(code) == 3 and code not in found:
                found.append(code)
        return found

    def own(self, tag):
        """The ISO 639-3 code a subtag itself names (not the members of a macrolanguage), or None."""
        return self.overlong.get(tag) or (tag if len(tag) == 3 else None)

    def subtag(self, iso):
        """The language subtag an ISO 639-3 code is written with (for a source keyed by such codes):
        that of the macrolanguage CLDR files the code under (plt under mg), its two-letter subtag,
        or the code itself."""
        iso = self.macro.get(iso, iso)
        return self.short.get(iso, iso)


def split_locale(stem):
    """(language, script or None) of a file named after a locale, or None for a regional or variant
    locale (only a language's own files and its scripts' are read)."""
    parts = re.split("[_-]", stem)
    if len(parts) == 1 and 2 <= len(parts[0]) <= 3 and parts[0].islower():
        return parts[0], None
    if len(parts) == 2 and 2 <= len(parts[0]) <= 3 and len(parts[1]) == 4 and parts[1].istitle():
        return parts[0], parts[1]
    return None


def exemplars_of(root, kind=None):
    """(the exemplar set's text, its draft level or None): the one with no alt (alternates are
    proposals, SLDR's "suspect" raw counts among them), or (None, None)."""
    for element in root.iter("exemplarCharacters"):
        if element.get("type") == kind and element.get("alt") is None:
            text = (element.text or "").strip()
            if text and text != "[]" and text != INHERITED:
                return text, element.get("draft")
    return None, None


def own_name(root, tag):
    """The language's name in its own locale file (an autonym), or ""."""
    names = root.find("localeDisplayNames/languages")
    if names is not None:
        for one in names.iter("language"):
            if one.get("type") == tag and one.get("alt") is None and one.text and one.text != INHERITED:
                return one.text.strip()
    return ""


def ldml_orthography(root, tag, script, name, source, validity, problems):
    main, _ = exemplars_of(root)
    auxiliary, _ = exemplars_of(root, "auxiliary")
    try:
        base = parse_set(main)
        auxiliary = parse_set(auxiliary) if auxiliary else []
    except (UnsupportedSet, ValueError, IndexError, KeyError) as exc:
        problems.append("%s %s %s: %s" % (source, tag, script, exc))
        return None
    return shaped(tag, script, name, own_name(root, tag), base, auxiliary, [], source, True, validity=validity)


def read_cldr(archive, codes, problems):
    found = collections.defaultdict(list)
    for name in sorted(archive.namelist()):
        if not (name.startswith("common/main/") and name.endswith(".xml")):
            continue
        locale = split_locale(name[len("common/main/"):-4])
        if locale is None:
            continue
        root = ElementTree.fromstring(archive.read(name))
        main, draft = exemplars_of(root)
        if main is None:
            continue
        tag, script = locale
        script = script or codes.likely.get(tag)
        one = ldml_orthography(root, tag, script, codes.names.get(tag, ""), "cldr", draft or "", problems)
        if one is not None and script:
            found[tag].append(one)
    return found


def read_sldr(path, codes, problems):
    """({subtag: [Orthography]} declared, the same for those SLDR's tools generated)."""
    declared, generated = collections.defaultdict(list), collections.defaultdict(list)
    with tarfile.open(path, "r:gz") as archive:
        members = sorted((m for m in archive.getmembers() if m.isfile()), key=lambda m: m.name)
        for member in members:
            parts = member.name.split("/")
            if len(parts) != 4 or parts[1] != "sldr" or not parts[3].endswith(".xml"):
                continue
            locale = split_locale(parts[3][:-4])
            if locale is None:
                continue
            try:
                root = ElementTree.fromstring(archive.extractfile(member).read())
            except ElementTree.ParseError as exc:
                problems.append("sldr %s: %s" % (parts[3], exc))
                continue
            main, draft = exemplars_of(root)
            if main is None:
                continue
            tag, script = locale
            identity = root.find("identity/special/%sidentity" % SLDR_NS)
            if identity is not None:
                script = script or identity.get("script")
                draft = draft or identity.get("draft")
            script = script or codes.likely.get(tag)
            draft = draft or SLDR_DEFAULT_DRAFT
            if draft in SLDR_LEFT_OUT or not script:
                continue
            name = ""
            for one in root.iter("%sname" % SLDR_NS):
                if one.get("{http://www.w3.org/XML/1998/namespace}lang") == "en" and one.text:
                    name = name or one.text.strip()
            source = "sldr-generated" if draft == "generated" else "sldr"
            one = ldml_orthography(root, tag, script, name or codes.names.get(tag, ""), source, draft, problems)
            if one is not None:
                (generated if draft == "generated" else declared)[tag].append(one)
    return declared, generated


# ---------------------------------------------------------------------------
# Google Fonts' language data
# ---------------------------------------------------------------------------

TOKEN = re.compile(r'\s*(?:(#[^\n]*)|([A-Za-z_][A-Za-z0-9_]*)|("(?:[^"\\]|\\.)*")|([{}:<>])|([-+.0-9A-Za-z]+))', re.S)
ESCAPE = re.compile(rb"\\(?:([0-7]{1,3})|x([0-9A-Fa-f]{1,2})|u([0-9A-Fa-f]{4})|U([0-9A-Fa-f]{8})|(.))", re.S)
PLAIN = {b"n": b"\n", b"t": b"\t", b"r": b"\r"}


def unescape(literal):
    """A text-format protobuf string's value (its escapes are of bytes: UTF-8)."""
    def replace(match):
        octal, hexa, short, long_, other = match.groups()
        if octal:
            return bytes([int(octal, 8)])
        if hexa:
            return bytes([int(hexa, 16)])
        if short or long_:
            return chr(int(short or long_, 16)).encode("utf-8")
        return PLAIN.get(other, other)
    return ESCAPE.sub(replace, literal[1:-1].encode("utf-8")).decode("utf-8")


def parse_textproto(text):
    """A text-format protobuf message as {field: [values]}, a nested message a dict of the same."""
    tokens = [match.groups() for match in TOKEN.finditer(text)]
    at = 0

    def message(closing):
        nonlocal at
        found = collections.OrderedDict()
        while at < len(tokens):
            comment, name, string, sign, word = tokens[at]
            at += 1
            if comment:
                continue
            if sign in ("}", ">") and closing:
                return found
            if not name:
                raise ValueError("field name expected")
            if tokens[at][3] == ":":
                at += 1
            _, word2, string2, sign2, other2 = tokens[at]
            if sign2 in ("{", "<"):
                at += 1
                value = message(True)
            elif string2 is not None:
                value = ""
                while at < len(tokens) and tokens[at][2] is not None:  # (adjacent strings are one)
                    value += unescape(tokens[at][2])
                    at += 1
            else:
                value = word2 if word2 is not None else other2
                at += 1
            found.setdefault(name, []).append(value)
        return found

    return message(False)


def exemplar_elements(text):
    """The elements of one of Google's exemplar lists: split at spaces, a sequence in braces one."""
    return [part[1:-1] if part.startswith("{") and part.endswith("}") and len(part) > 2 else part
            for part in (text or "").split()]


SAMPLE_FIELDS = ("styles", "tester", "specimen_48", "specimen_36", "specimen_32", "specimen_21", "specimen_16")
# (not the mastheads and posters: a few letters picked for their shapes)


def read_gflanguages(path, scripts, counter, problems, listed=None):
    """({subtag: [Orthography]} from exemplar characters, {subtag: [Evidence]} counted from sample
    texts); scripts is filled with Google's script names by ISO 15924 code, and listed (when given)
    with the scripts Google's data names for each subtag, characters or not."""
    declared, counted = collections.defaultdict(list), collections.defaultdict(list)
    files = {}
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile() or not member.name.endswith(".textproto"):
                continue
            folder = member.name.split("/")[-2]
            if folder in ("languages", "scripts") and "/data/" in member.name:
                files[member.name] = (folder, archive.extractfile(member).read().decode("utf-8"))
    languages = []
    for name in sorted(files):
        folder, text = files[name]
        try:
            fields = parse_textproto(text)
        except (ValueError, IndexError) as exc:
            problems.append("gflanguages %s: %s" % (name.split("/")[-1], exc))
            continue
        if folder == "scripts":
            scripts.setdefault(fields["id"][0], fields["name"][0].replace("\N{ZERO WIDTH SPACE}", "").strip())
        else:
            languages.append(fields)
    seen = set()
    for fields in sorted(languages, key=lambda f: (len(f["id"][0].split("_")), f["id"][0])):
        tag, script = fields["language"][0], fields["script"][0]
        if not split_locale(tag) or (tag, script) in seen:  # (a variant subtag; a region's file after the language's own)
            continue
        if listed is not None and script not in listed.setdefault(tag, []):
            listed[tag].append(script)
        name = (fields.get("preferred_name") or fields.get("name") or [""])[0]
        autonym = (fields.get("autonym") or [""])[0]
        speakers = int((fields.get("population") or [0])[0] or 0)
        historical = (fields.get("historical") or ["false"])[0] == "true"
        exemplars = (fields.get("exemplar_chars") or [{}])[0]
        base = exemplar_elements((exemplars.get("base") or [""])[0])
        if base:
            one = shaped(tag, script, name, autonym, base, exemplar_elements((exemplars.get("auxiliary") or [""])[0]),
                         exemplar_elements((exemplars.get("marks") or [""])[0]), "gflanguages", False,
                         speakers=speakers, historical=historical)
            if one is not None:
                declared[tag].append(one)
                seen.add((tag, script))
            continue
        sample = (fields.get("sample_text") or [{}])[0]
        text = "\n".join((sample.get(field) or [""])[0] for field in SAMPLE_FIELDS)
        counts = dict((unit, (times, times)) for unit, times in counter.count(text).items())
        one = counter.evidence(counts, sum(times for times, _ in counts.values()), tag, name, autonym,
                               "gflanguages-text", wanted=script, speakers=speakers, historical=historical)
        if one is not None:
            counted[tag].append(one)
            seen.add((tag, script))
    return declared, counted


# ---------------------------------------------------------------------------
# Counted texts
# ---------------------------------------------------------------------------

class Counter(object):
    """Counts the letters of a text and makes an orthography of those that pass the floor (the
    module's own words say the rule)."""

    def __init__(self, scripts_path, script_names):
        self.ranges, self.script_names, self.known = [], script_names, {}
        with open(scripts_path, encoding="utf-8") as handle:
            for line in handle:
                line = line.split("#")[0].strip()
                if not line:
                    continue
                span, script = [part.strip() for part in line.split(";")]
                low, _, high = span.partition("..")
                self.ranges.append((int(low, 16), int(high or low, 16), script))
        self.ranges.sort()
        self.lows = [low for low, _, _ in self.ranges]
        # Unicode's script name: its ISO 15924 code, PropertyValueAliases.txt's (Scripts fills it). Without
        # it a script was known only by UNICODE_SCRIPTS or Google's name for it, and a text in Warang Citi
        # (Google: "Varang Kshiti") counted for nothing.
        self.unicode_codes = {}

    def code_of_script(self, script):
        """The ISO 15924 code of one of Unicode's script names (Scripts.txt's), or None."""
        return self.unicode_codes.get(script) or UNICODE_SCRIPTS.get(script) or next(
            (code for code, title in sorted(self.script_names.items()) if title.replace(" ", "_") == script), None)

    def script_of(self, ch):
        """Unicode's script of a character (Scripts.txt), "Unknown" outside its ranges."""
        if ch not in self.known:
            at = bisect.bisect_right(self.lows, ord(ch)) - 1
            low, high, script = self.ranges[at] if at >= 0 else (0, -1, "")
            self.known[ch] = script if low <= ord(ch) <= high else "Unknown"
        return self.known[ch]

    def count(self, text):
        """{unit: times} of a text: its letters in small, each with the marks on it (clusters_of);
        what is no letter is skipped, and a mark after no letter too."""
        counts = collections.Counter()
        for cluster in clusters_of(text):
            if category(cluster[0]).startswith("L"):
                lower = unicodedata.normalize("NFC", cluster.lower())
                counts[lower if len(clusters_of(lower)) == 1 else cluster] += 1
        return counts

    def orthography(self, counts, size, tag, name, autonym, source, wanted=None, **more):
        """An Orthography of the units counted that pass the floor (evidence() says how), or None."""
        found = self.evidence(counts, size, tag, name, autonym, source, wanted=wanted, **more)
        return orthography_of([found]) if found is not None else None

    def evidence(self, counts, size, tag, name, autonym, source, wanted=None, **more):
        """The Evidence of the units counted ({unit: (weight, times)}: weight is what its share is
        taken of, times the word forms or places it stands in): those that pass the floor, and every
        one seen with its share, or None: too short a text (size: its letters), or (wanted: an ISO
        15924 code) not the script stated."""
        by_script = collections.Counter()
        for unit, (weight, _) in counts.items():
            by_script[self.script_of(unit[0])] += weight
        for none in ("Common", "Inherited", "Unknown"):
            by_script.pop(none, None)
        if not by_script or size < INFERRED_LETTERS:
            return None
        script = max(sorted(by_script), key=lambda one: by_script[one])
        code = self.code_of_script(script)
        if code is None or (wanted is not None and wanted != code
                            and SCRIPT_NAMES.get(wanted, wanted) != SCRIPT_NAMES.get(code, code)):
            return None
        clustered = script in CLUSTERED_SCRIPTS
        weights, places = collections.Counter(), collections.Counter()
        for unit, (weight, times) in counts.items():
            if self.script_of(unit[0]) not in (script, "Common"):
                continue
            for part in ([unit] if clustered else list(unit)):  # (letters and marks one by one outside the alphabets)
                weights[part] += weight
                places[part] += times
        letters = sum(weight for unit, weight in weights.items() if not is_mark(unit[0]))
        if not letters:
            return None
        kept = [unit for unit in sorted(weights, key=lambda unit: (-weights[unit], unit))
                if weights[unit] >= letters * INFERRED_SHARE and places[unit] >= INFERRED_TIMES]
        seen = dict((unit, weight / float(letters)) for unit, weight in weights.items() if weight > 0)
        return Evidence(source, tag, code, kept, seen, size, name=name, autonym=autonym, **more)


class Evidence(object):
    """What one inferred source gives of a language in one script, before an orthography is made of
    it: kept, the letters its rule keeps (small letters, the most frequent first); seen, every letter
    of the script it has with its share of the letters counted, or None for a source that gives no
    counts (SLDR's generated exemplars: what it has is what it keeps); size, the letters counted (0:
    not given); profile, the text's trigram counts where they can be had (to tell one text counted
    twice from two texts)."""

    def __init__(self, source, tag, script, kept, seen, size, auxiliary=(), name="", autonym="", validity="",
                 speakers=0, historical=False):
        self.source, self.tag, self.script, self.kept, self.seen, self.size = source, tag, script, list(kept), seen, size
        self.auxiliary, self.name, self.autonym, self.validity = list(auxiliary), name, autonym, validity
        self.speakers, self.historical, self.profile = speakers, historical, None
        self.given = None  # the Orthography a source gave as it is (SLDR's), kept when it stands alone

    def has(self, unit):
        return unit in (self.seen if self.seen is not None else self.kept)


def generated_evidence(one):
    """The Evidence of one of SLDR's generated orthographies: its small letters and its marks, as
    SLDR gives them, with no counts."""
    capitals = set(capital_of(item) for item in one.base)
    kept = [item for item in one.base if item not in capitals] + list(one.marks)
    found = Evidence(one.source, one.tag, one.script, kept, None, 0, auxiliary=one.auxiliary, name=one.name,
                     autonym=one.autonym, validity=one.validity, speakers=one.speakers, historical=one.historical)
    found.given = one
    return found


def reinforced(found):
    """The letters of several pieces of evidence of one language in one script (independent ones:
    independent() sets the others aside): a letter is kept when one source's rule keeps it and
    another source has it too, or when it alone makes REINFORCED_ALONE times the share in the source
    that keeps it. One piece alone gives what its rule keeps."""
    if len(found) == 1:
        return list(found[0].kept)
    kept = []
    for one in found:
        # A source without counts (SLDR's generated exemplars) cannot say how frequent a letter is: its
        # letters go only when the counted sources beside it are large enough for their silence to mean
        # something (SILENCE_LETTERS between them). A sample text of 1,200 letters took 13 of Syloti
        # Nagri's letters from SLDR's set otherwise.
        counted = sum(other.size for other in found if other is not one and other.seen is not None)
        for unit in one.kept:
            if unit in kept:
                continue
            if any(other.has(unit) for other in found if other is not one) or (
                    one.seen is not None and one.seen.get(unit, 0) >= INFERRED_SHARE * REINFORCED_ALONE) or (
                    one.seen is None and counted < SILENCE_LETTERS):
                kept.append(unit)
    return kept


def orthography_of(found):
    """The Orthography several pieces of evidence of one language in one script give together (the
    best-ranked source first: its name and what else it says of the language are kept), or None."""
    first = found[0]
    if len(found) == 1 and first.given is not None:
        first.given.rests = [(first.source, first.size)]
        return first.given
    auxiliary = [item for one in found for item in one.auxiliary]
    made = shaped(first.tag, first.script, first.name, first.autonym, reinforced(found), auxiliary, [], first.source, True,
                  validity=first.validity, speakers=first.speakers, historical=first.historical)
    if made is not None:
        made.rests = [(one.source, one.size) for one in found]
    return made


def text_profile(text):
    """The trigram counts of a text as An Crubadan's 2010 files count them: every run of three
    characters of every word, in small letters, the word between "<" and ">"."""
    grams = collections.Counter()
    words = "".join(ch.lower() if ch.isalpha() or is_mark(ch) or ch == "'" else " " for ch in text).split()
    for word in words:
        word = "<%s>" % word
        for at in range(len(word) - 2):
            grams[word[at:at + 3]] += 1
    return grams


def cosine(one, other):
    """How alike two trigram counts are, from 0 to 1 (1: the same text)."""
    if not one or not other:
        return 0.0
    dot = sum(count * other.get(gram, 0) for gram, count in one.items())
    return dot / (sum(v * v for v in one.values()) ** 0.5 * sum(v * v for v in other.values()) ** 0.5)


def independent(found):
    """The pieces of evidence of one language in one script that are independent of each other, in
    the order given. Google's sample text is an excerpt of the declaration: it adds nothing where
    the whole text is there. One of An Crubadan's trigram files that counts the declaration's own
    text (many of its smaller corpora are that one document) gives way to the text itself."""
    whole = next((one for one in found if one.source == "udhr2"), None)
    if whole is None:
        return list(found)
    kept = []
    for one in found:
        if one.source == "gflanguages-text":
            continue
        if one.source == "crubadan-trigrams" and cosine(one.profile, whole.profile) >= SAME_TEXT:
            continue
        kept.append(one)
    return kept


def read_unilex(path, counter, codes, wanted, problems):
    """{subtag: [Evidence]} counted from Unilex's word frequencies, for the subtags wanted(subtag)
    says are still needed (the archive is large: the others are not read)."""
    found = collections.defaultdict(list)
    with tarfile.open(path, "r:gz") as archive:
        members = sorted((m for m in archive.getmembers() if m.isfile() and "/data/frequency/" in m.name
                          and m.name.endswith(".txt")), key=lambda m: m.name)
        for member in members:
            locale = split_locale(member.name.split("/")[-1][:-4])
            if locale is None or not wanted(locale[0]):
                continue
            tag, script = locale
            counts, size = {}, 0
            for line in archive.extractfile(member).read().decode("utf-8").split("\n")[1:]:
                form, _, frequency = line.partition("\t")
                if not form or form.startswith("#") or not frequency.strip().isdigit():
                    continue
                weight = int(frequency)  # (per billion words: a share, whatever the corpus's size)
                for unit, times in counter.count(form).items():
                    held = counts.get(unit, (0, 0))
                    counts[unit] = (held[0] + weight * times, held[1] + 1)
                    size += times  # (the letters of the distinct word forms: what the 1,000 are asked of)
            one = counter.evidence(counts, size, tag, codes.names.get(tag, ""), "", "unilex", wanted=script)
            if one is not None:
                found[tag].append(one)
    return found


def trigram_counts(lines, counter):
    """({unit: (weight, times)}, the letters counted) of character trigram counts, one "count abc"
    a line, as An Crubadan's 2010 files give them: every run of three characters of every word, the
    word between "<" and ">". Each character of a text is the middle one of exactly one trigram, so
    the middle characters are counted, and the two markers, which are no letters, never count. A
    letter is taken with the combining mark after it (one mark: the trigram shows no further), a mark
    after another mark alone, and a mark after no letter is skipped, as in a text. times is the
    number of different trigrams the unit is the middle of: three stands for the three word forms,
    which trigrams do not show."""
    counts, size = {}, 0
    for line in lines:
        number, _, gram = line.rstrip("\r\n").partition(" ")
        if not number.isdigit() or len(gram) != 3:
            continue
        before, ch, after = gram
        if category(ch).startswith("L"):
            unit = next(iter(counter.count(ch + after if is_mark(after) else ch)), None)
        else:
            unit = ch if is_mark(ch) and is_mark(before) else None
        if unit is None:
            continue
        held = counts.get(unit, (0, 0))
        counts[unit] = (held[0] + int(number), held[1] + 1)
        if not is_mark(unit[0]):
            size += int(number)
    return counts, size


def read_crubadan(paths, counter, codes, wanted, problems):
    """({subtag: [Evidence]} counted from the word frequencies of An Crubadan's archives, the same
    from the character trigrams of its 2010 files), for the subtags wanted(subtag) says are needed.
    An archive is named by the writing system's code, a BCP 47 tag; the 2010 files by codes of
    An Crubadan's own, which their table gives the ISO 639-3 codes of (MISFILED: but for three).
    Each piece from a trigram file keeps the file's ISO 639-3 code (iso) and its trigram counts
    (profile)."""
    words, trigrams = collections.defaultdict(list), collections.defaultdict(list)
    for code, capture, _, _ in CRUBADAN_ARCHIVES:
        locale = split_locale(code)
        if locale is None or not wanted(locale[0]):
            continue
        tag, script = locale
        counts, size = {}, 0
        with zipfile.ZipFile(paths["crubadan-%s-%s.zip" % (code, capture)]) as archive:
            for line in archive.read("%s-words.txt" % code).decode("utf-8").split("\n"):
                form, _, frequency = line.rpartition(" ")
                if not form or not frequency.strip().isdigit():
                    continue
                for unit, times in counter.count(form).items():
                    held = counts.get(unit, (0, 0))
                    counts[unit] = (held[0] + int(frequency) * times, held[1] + 1)
                    size += times  # (as for Unilex: the letters of the distinct word forms)
        one = counter.evidence(counts, size, tag, codes.names.get(tag, ""), "", "crubadan", wanted=script)
        if one is not None:
            words[tag].append(one)
    with zipfile.ZipFile(paths[CRUBADAN_TRIGRAMS]) as archive:
        for line in archive.read("crubadan/table.txt").decode("utf-8").split("\n"):
            parts = [part.strip() for part in line.split("\t")]
            if len(parts) != 3 or len(parts[1]) != 3:
                continue
            tag = codes.subtag(MISFILED.get(parts[1], parts[1]))
            if not wanted(tag):
                continue
            lines = archive.read("crubadan/%s-3grams.txt" % parts[0]).decode("utf-8").split("\n")
            counts, size = trigram_counts(lines, counter)
            one = counter.evidence(counts, size, tag, codes.names.get(tag, ""), "", "crubadan-trigrams")
            if one is not None:
                one.iso, one.profile = parts[1], collections.Counter()
                for line in lines:
                    number, _, gram = line.rstrip("\r\n").partition(" ")
                    if number.isdigit() and len(gram) == 3:
                        one.profile[gram.lower()] += int(number)
                trigrams[tag].append(one)
    return words, trigrams


def read_udhr2(path, counter, codes, wanted, problems):
    """({subtag: [Evidence]} counted from the whole texts of the Universal Declaration of Human
    Rights, for the subtags wanted(subtag) says are needed; {ISO 639-3 code: the trigram counts of its
    text} of every text). A file is named by an ISO 639-3 code (MISFILED: but for one), read as the
    subtag CLDR writes it with; a language's own file and the files named by a script are read, not
    the variants (a region, a spelling, a second translation), nor the five files named by a number."""
    found, profiles = collections.defaultdict(list), {}
    with zipfile.ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            code, _, variant = name.split("/")[-1].rpartition(".")[0].partition("_")
            if not name.endswith(".txt") or len(code) != 3 or not code.isalpha():
                continue
            script = variant.title() if variant.title() in UDHR_SCRIPTS and variant.islower() else None
            if variant and script is None:
                continue
            text = archive.read(name).decode("utf-8")
            profile = text_profile(text)
            profiles.setdefault(MISFILED.get(code, code), profile)
            tag = codes.subtag(MISFILED.get(code, code))
            if not wanted(tag):
                continue
            counts = dict((unit, (times, times)) for unit, times in counter.count(text).items())
            one = counter.evidence(counts, sum(times for times, _ in counts.values()), tag, codes.names.get(tag, ""), "",
                                   "udhr2", wanted=script)
            if one is not None:
                one.profile = profile
                found[tag].append(one)
    return found, profiles


def misfiled(trigrams, profiles):
    """Lines for the trigram files read whose nearest text of the declaration is another code's (a
    cosine of MISFILED_COSINE or more, and clearly more than its own code's text has): candidates for
    MISFILED, to be checked by hand."""
    lines = []
    for tag in sorted(trigrams):
        for one in trigrams[tag]:
            near = sorted(((cosine(one.profile, profile), code) for code, profile in profiles.items()), reverse=True)
            own = MISFILED.get(one.iso, one.iso)
            if near and near[0][0] >= MISFILED_COSINE and near[0][1] != own and (
                    own not in profiles or cosine(one.profile, profiles[own]) < near[0][0] - 0.05):
                lines.append("An Crubadan's trigram file for %s is the declaration's text for %s (cosine %.2f): "
                             "see MISFILED" % (one.iso, near[0][1], near[0][0]))
    return lines


# ---------------------------------------------------------------------------
# Keyboard layouts (Language Tools)
# ---------------------------------------------------------------------------

JS_TOKEN = re.compile(r"""\s+|//[^\n]*|/\*.*?\*/|('(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*")|([{}\[\]:,+;()=])|([^\s{}\[\]:,+;()='"]+)""",
                      re.S)
JS_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}


def js_string(literal):
    """A JavaScript string literal's value: its escapes decoded (\\uXXXX are UTF-16 code units, so
    a pair of surrogates is one character; a lone surrogate becomes U+FFFD, which no row keeps)."""
    body, found, at = literal[1:-1], [], 0
    while at < len(body):
        ch = body[at]
        if ch != "\\" or at + 1 == len(body):
            found.append(ch)
            at += 1
            continue
        escape = body[at + 1]
        if escape == "u" and body[at + 2:at + 3] == "{":
            end = body.index("}", at)
            found.append(chr(int(body[at + 3:end], 16)))
            at = end + 1
        elif escape == "u":
            found.append(chr(int(body[at + 2:at + 6], 16)))
            at += 6
        elif escape == "x":
            found.append(chr(int(body[at + 2:at + 4], 16)))
            at += 4
        else:
            found.append(JS_ESCAPES.get(escape, escape))
            at += 2
    return "".join(found).encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")


def js_object(text):
    """The first object literal of a layout file, as dicts, lists, and strings (a string added to
    another is one); what is none of these (a number, a name, a function) as its first word."""
    tokens = []
    for match in JS_TOKEN.finditer(text):
        string, sign, word = match.groups()
        if string is not None:
            tokens.append(("s", js_string(string)))
        elif sign is not None:
            tokens.append(("p", sign))
        elif word is not None:
            tokens.append(("w", word))
    at = next(index for index, token in enumerate(tokens) if token == ("p", "{"))

    def value(at):
        kind, part = tokens[at]
        if (kind, part) == ("p", "{"):
            found, at = collections.OrderedDict(), at + 1
            while tokens[at] != ("p", "}"):
                if tokens[at] == ("p", ","):
                    at += 1
                    continue
                key = tokens[at][1]
                at += 2  # (the key and its colon)
                found[key], at = value(at)
            return found, at + 1
        if (kind, part) == ("p", "["):
            found, at = [], at + 1
            while tokens[at] != ("p", "]"):
                if tokens[at] == ("p", ","):
                    at += 1
                    continue
                one, at = value(at)
                found.append(one)
            return found, at + 1
        if kind == "s":
            found, at = part, at + 1
            while at + 1 < len(tokens) and tokens[at] == ("p", "+") and tokens[at + 1][0] == "s":
                found, at = found + tokens[at + 1][1], at + 2
            return found, at
        depth, first = 0, part  # (anything else: skipped to the next comma or closing sign at its level)
        while True:
            kind, part = tokens[at]
            if kind == "p" and part in "{[(":
                depth += 1
            elif kind == "p" and part in "}])":
                if depth == 0:
                    return first, at
                depth -= 1
            elif (kind, part) == ("p", ",") and depth == 0:
                return first, at
            at += 1

    return value(at)[0]


def key_outputs(layer):
    """What each key of a layer's string types: a character, or the text between {{ and }} (its
    label set apart where one is given: {{S||label||text}})."""
    found, at = [], 0
    while at < len(layer):
        end = layer.find("}}", at + 2) if layer.startswith("{{", at) else -1
        if end < 0:
            found.append(layer[at])
            at += 1
            continue
        inner = layer[at + 2:end]
        found.append(re.split(r"\|\|?", inner)[-1] if inner.startswith("S|") else inner)
        at = end + 2
    return found


def layout_outputs(text):
    """([(the layer's name, [what each of its keys types])], [what each of its rules writes]) of a
    layout file (Google's virtual keyboard format, as Language Tools writes it): the mappings of
    each layer (shift, AltGr, caps lock, and so on), then the transform's replacements, which turn
    what was typed into letters (a phonetic keyboard composes most of its letters so)."""
    layout = js_object(text)
    layers = []
    for name, layer in (layout.get("mappings") or {}).items():
        for prefix, keys in (layer.items() if isinstance(layer, dict) else [("", layer)]):
            if isinstance(keys, str):
                layers.append((name + ("/" + prefix if prefix else ""), key_outputs(keys)))
    rules = layout.get("transform") or {}
    return layers, [value for value in rules.values() if isinstance(value, str)] if isinstance(rules, dict) else []


class Scripts(object):
    """Unicode's scripts of characters (Scripts.txt, ScriptExtensions.txt) by ISO 15924 code
    (PropertyValueAliases.txt names each script's code)."""

    def __init__(self, counter, extensions_path, aliases_path):
        self.counter, self.codes, self.names, self.extended = counter, {}, {}, {}
        with open(aliases_path, encoding="utf-8") as handle:
            for line in handle:
                parts = [part.strip() for part in line.split("#")[0].split(";")]
                if len(parts) >= 3 and parts[0] == "sc":
                    self.codes[parts[2]], self.names[parts[1]] = parts[1], parts[2]
        counter.unicode_codes.update(self.codes)  # (a counted text's script by its own code)
        with open(extensions_path, encoding="utf-8") as handle:
            for line in handle:
                line = line.split("#")[0].strip()
                if line:
                    span, codes = [part.strip() for part in line.split(";")]
                    low, _, high = span.partition("..")
                    for code in range(int(low, 16), int(high or low, 16) + 1):
                        self.extended[code] = codes.split()

    def code_of(self, ch):
        """The ISO 15924 code of a character's script (Zyyy: Common, Zinh: Inherited, Zzzz: unknown)."""
        return self.codes.get(self.counter.script_of(ch), "Zzzz")

    def mark_of(self, ch, script):
        """Whether a combining mark belongs to a script: its own, or shared with it (Script_Extensions),
        or, in one of the alphabets (CLUSTERED_SCRIPTS), whose letters take the diacritics of
        Unicode's general blocks, an Inherited one."""
        code = self.code_of(ch)
        if code == script or script in self.extended.get(ord(ch), ()):
            return True
        return code == "Zinh" and self.names.get(script, "") in CLUSTERED_SCRIPTS


BASIC_LATIN = [chr(code) for code in range(0x61, 0x7B)]  # a to z (their capitals are added as any letter's are)


def keyboard_units(text, script, scripts):
    """The letters and marks of a script that a layout's text types, in order, each once: letters of
    the script, or modifier letters of no script of their own (the modifier apostrophe; not a
    micro sign a Tifinagh layout types); marks of the script or shared with it. In an alphabet
    (CLUSTERED_SCRIPTS) a letter is kept with the marks on it, as a counted text's are; elsewhere
    letters and marks one by one. Private-use and unassigned code points are no letters (the pinned
    UnicodeData.txt says which are assigned), and are dropped."""
    clustered = scripts.names.get(script, "") in CLUSTERED_SCRIPTS
    found = []
    for cluster in clusters_of(text.replace("{{", "").replace("}}", "")):
        if category(cluster[0]).startswith("L"):
            code = scripts.code_of(cluster[0])
            if code != script and not (code == "Zyyy" and category(cluster[0]) == "Lm"):
                continue
            if clustered:
                parts = [cluster if all(scripts.mark_of(ch, script) for ch in cluster[1:]) else cluster[0]]
            else:
                parts = [cluster[0]] + [ch for ch in cluster[1:] if scripts.mark_of(ch, script)]
        else:
            parts = [ch for ch in cluster if is_mark(ch) and scripts.mark_of(ch, script)]
        for part in parts:
            if part not in found:
                found.append(part)
    return found


def keyboard_reading(text, script, scripts):
    """(the letters and marks a layout's keys and rules type in a script, the layers left out as a
    Latin fallback): every layer's keys and every rule's replacement, in NFC; for a script other
    than Latin, a layer all of whose letters are Latin is the keyboard's Latin fallback (the
    layers with Control, or caps lock, often are) and is not read; for Latin, a to z and their
    capitals are taken with what the layout adds."""
    layers, rules = layout_outputs(text)
    found, fallback = (list(BASIC_LATIN) if script == "Latn" else []), []
    for name, keys in layers:
        letters = [ch for key in keys for ch in key if category(ch).startswith("L")]
        if script != "Latn" and letters and all(scripts.code_of(ch) == "Latn" for ch in letters):
            fallback.append(name)
            continue
        for key in keys:
            found.extend(unit for unit in keyboard_units(key, script, scripts) if unit not in found)
    for replacement in rules:
        found.extend(unit for unit in keyboard_units(replacement, script, scripts) if unit not in found)
    return found, fallback


def foreign_letters(text, script, scripts, fallback=()):
    """The letters (general category L) of a script other than the layout's own, Latin, and Common
    or Inherited that its layers (but those of fallback) and rules type, in NFC, each once, a capital
    with its small letter (KEYBOARD_FOREIGN says what they show)."""
    layers, rules = layout_outputs(text)
    found = []
    for typed in [key for name, keys in layers if name not in fallback for key in keys] + rules:
        for ch in unicodedata.normalize("NFC", typed):
            if category(ch).startswith("L") and scripts.code_of(ch) not in (script, "Latn", "Zyyy", "Zinh"):
                small = ch.lower() if len(ch.lower()) == 1 else ch
                if small not in found:
                    found.append(small)
    return found


def own_units(units, script):
    """What of a layout's letters and marks an English keyboard does not type: in Latin, all but a to
    z and their capitals; elsewhere, all of them."""
    if script != "Latn":
        return list(units)
    return [unit for unit in units if unit.lower() not in BASIC_LATIN]


def read_keyboards(paths, scripts, problems=None):
    """({(ISO 639-3 code, ISO 15924 code): (the layout read, its letters and marks)}, the layouts
    refused as [(layout, code, script, letters and marks, of which beyond English, the letters of
    other scripts it types)]): of the layouts of KEYBOARDS, each language and script's that types the
    most letters and marks of the script (the first of equals), if it passes the floor and types no
    more than KEYBOARD_FOREIGN letters of another script."""
    chosen, refused = collections.OrderedDict(), []
    for name, iso, script, _ in KEYBOARDS:
        with open(paths["%s.js" % name], encoding="utf-8") as handle:
            text = handle.read()
        try:
            units, fallback = keyboard_reading(text, script, scripts)
            foreign = foreign_letters(text, script, scripts, fallback)
        except (ValueError, IndexError, KeyError, StopIteration) as exc:
            if problems is not None:
                problems.append("keyboard %s: %r" % (name, exc))
            continue
        if (len(units) < KEYBOARD_FLOOR or len(own_units(units, script)) < KEYBOARD_OWN
                or len(foreign) > KEYBOARD_FOREIGN):
            refused.append((name, iso, script, len(units), len(own_units(units, script)), foreign))
            continue
        if (iso, script) not in chosen or len(units) > len(chosen[(iso, script)][1]):
            chosen[(iso, script)] = (name, units)
    return chosen, refused


# ---------------------------------------------------------------------------
# Putting them together
# ---------------------------------------------------------------------------

def glottolog_tables(folder):
    """({ISO code: Glottolog's row, a language's before a dialect's or a family's}) from the table
    families.py downloads (its own pins)."""
    sys.path.insert(0, HERE)
    try:
        import families
    finally:
        sys.path.remove(HERE)
    paths = families.download(folder)
    by_iso = {}
    for row in sorted(families.table(paths["cldf/languages.csv"]),
                      key=lambda row: (families.LEVELS.index(row["Level"]), row["ID"])):
        if row["ISO639P3code"] and row["Family_ID"] != families.BOOKKEEPING:  # (not its retired and spurious entries)
            by_iso.setdefault(row["ISO639P3code"], row)
    return by_iso, families


def written_in(items, scripts):
    """The ISO 15924 code of the script most of an orthography's letters are in, or None."""
    by_script = collections.Counter(scripts.code_of(item[0]) for item in items if category(item[0]).startswith("L"))
    for none in ("Zyyy", "Zinh", "Zzzz"):
        by_script.pop(none, None)
    return max(sorted(by_script), key=lambda code: by_script[code]) if by_script else None


def second_scripts(declared, codes, hyperglot_written, scripts):
    """{ISO code: [Orthography]}: what the declared sources give of Hyperglot's languages in scripts
    Hyperglot does not give them in (Javanese in Javanese, Kazakh in Arabic), each script from the
    first source (declared, in the order of preference: [(key, {subtag: [Orthography]})]) that has it.
    A script is the one most of an orthography's letters are in (written_in), on both sides. Only a
    subtag that names the language itself counts: a macrolanguage's subtag (uz, ff, sw) says nothing
    of which of its members Hyperglot's is (Uzbek in Arabic is Southern Uzbek's, not Northern's)."""
    found = collections.defaultdict(list)
    for _, by_tag in declared:
        for tag in sorted(by_tag):
            iso = codes.own(tag)
            if iso not in hyperglot_written:
                continue
            for one in by_tag[tag]:
                written = written_in(one.base, scripts)
                if written is None or written in [code for _, code in hyperglot_written[iso]] or written in [
                        written_in(other.base, scripts) for other in found[iso]]:
                    continue
                found[iso].append(one)
    return dict((iso, ones) for iso, ones in found.items() if ones)


def plain_name(name, *scripts):
    """A language's name without the script a source adds to it ("Bassa (Latin)", "Wancho Naga,
    Latin"), for its row in another script; the script by any of the names given (Google calls Ho's
    text "Ho, Warang Citi" and the script itself Varang Kshiti)."""
    for script in scripts:
        for ending in (" (%s)" % script, ", %s" % script):
            if script and name.endswith(ending):
                return name[:-len(ending)]
    return name


def build(paths, glottolog_folder, texts, keyboards=None):
    with open(LANGUAGES_FILE, encoding="utf-8") as handle:
        hyperglot_rows = json.load(handle)
    hyperglot = set(row[0] for row in hyperglot_rows["orthographies"])
    by_iso, families = glottolog_tables(glottolog_folder)
    problems, script_names = [], {}
    pinned_categories(paths["unicode-%s-UnicodeData.txt" % UNICODE_VERSION])
    archive = zipfile.ZipFile(paths["cldr-common-%s.zip" % CLDR_VERSION])
    codes = Codes(archive)
    counter = Counter(paths["unicode-%s-Scripts.txt" % UNICODE_VERSION], script_names)
    scripts = Scripts(counter, paths["unicode-%s-ScriptExtensions.txt" % UNICODE_VERSION],
                      paths["unicode-%s-PropertyValueAliases.txt" % UNICODE_VERSION])
    said_scripts = {}  # subtag: the ISO 15924 codes a source names for it, with or without characters
    gf, gf_text = read_gflanguages(paths["lang-%s.tar.gz" % GF_TAG], script_names, counter, problems, said_scripts)
    cldr = read_cldr(archive, codes, problems)
    sldr, sldr_generated = read_sldr(paths["sldr-%s.tar.gz" % SLDR_TAG], codes, problems)
    placed_by_hand = set(families.PLACED)
    # One name per script, for every row and every lookup: Hyperglot's, else Google's, else Unicode's
    # (Tai Yo). Counted rows were keyed by a name of their own (Google's or the bare code) and layouts
    # by this one, so a script Google does not name could miss its counted row.
    title_of_code = lambda code: (SCRIPT_NAMES.get(code) or script_names.get(code)
                                  or scripts.names.get(code, code).replace("_", " "))
    script_of = lambda one: title_of_code(one.script)
    unicode_name = lambda code: scripts.names.get(code, "").replace("_", " ")  # (for plain_name)
    # The scripts Google's data states for each language, whether or not it gives characters or a text
    # that counts (said_scripts gets CLDR's too, further down).
    stated = dict((tag, set(title_of_code(code) for code in found)) for tag, found in said_scripts.items())
    glottolog = families.download(glottolog_folder)
    # A language Hyperglot describes through its members, by Glottolog's classification: Akan (aka),
    # whose dialects Twi and Fante Hyperglot describes. CLDR files Twi under ak and has no alias for
    # aka, so An Crubadan's aka file found no code of Hyperglot's and made a row of its own.
    through_members = families.described_through(families.table(glottolog["cldf/languages.csv"]),
                                                 families.parents_of(glottolog["cldf/classification.nex"]), hyperglot)

    no_language = set()

    def iso_of(tag):
        """The code a subtag's rows take: of the codes it may stand for, the first Glottolog has or
        families.py places by hand. None for Hyperglot's language (or one Hyperglot describes through
        its members), and for a subtag that names no language Glottolog knows (ISO 639-5 groups as
        "ber" and "gem", "mis", private-use codes)."""
        found = codes.isos(tag)
        if not found or any(code in hyperglot or code in through_members for code in found):
            return None
        code = next((code for code in found if code in by_iso or code in placed_by_hand), None)
        if code is None:
            no_language.add(tag)
        return code

    taken, rows_by_source = {}, collections.OrderedDict()  # taken: {ISO code: [Orthography]}
    declared = (("gflanguages", gf), ("cldr", cldr), ("sldr", sldr))
    for key, found in declared:  # declared: the first that has it, alone
        for tag in sorted(found):
            iso = iso_of(tag)
            if iso is not None and iso not in taken:
                taken[iso] = found[tag]
    hyperglot_written = collections.defaultdict(list)  # ISO code: [(name, the script its letters are in)]
    for row in hyperglot_rows["orthographies"]:
        base = hyperglot_rows["texts"][row[7]].split()
        hyperglot_written[row[0]].append((row[1], written_in(base, scripts)))
    # A declared orthography of a Hyperglot language in a script Hyperglot does not give it in is kept,
    # as a keyboard layout's is (second_scripts says which), under Hyperglot's name for the language.
    second = second_scripts(declared, codes, hyperglot_written, scripts)
    for iso in sorted(second):
        name, written = hyperglot_written[iso][0]
        for one in second[iso]:
            one.name = plain_name(name, title_of_code(written), unicode_name(written))
        taken[iso] = second[iso]
    needed = lambda tag: iso_of(tag) is not None and iso_of(tag) not in taken  # (no declared source has it)
    generated = dict((tag, [generated_evidence(one) for one in found]) for tag, found in sldr_generated.items())
    unilex = read_unilex(paths["unilex-%s.tar.gz" % UNILEX_COMMIT[:8]], counter, codes, needed, problems)
    crubadan, crubadan_trigrams = read_crubadan(texts, counter, codes, needed, problems)
    udhr2, profiles = read_udhr2(texts[UDHR2], counter, codes, needed, problems)
    problems.extend(misfiled(crubadan_trigrams, profiles))
    pieces = collections.defaultdict(dict)  # ISO code: {script's name: [Evidence], the best-ranked source first}
    for key, found in (("sldr-generated", generated), ("unilex", unilex), ("crubadan", crubadan),
                       ("crubadan-trigrams", crubadan_trigrams), ("udhr2", udhr2), ("gflanguages-text", gf_text)):
        for tag in sorted(found):
            iso = iso_of(tag)
            if iso is None or iso in taken:
                continue
            for one in found[tag]:
                if key.startswith("crubadan") or key == "udhr2":
                    # An Crubadan's script and the declaration's are the ones counted: where Google's
                    # data states the language's scripts and this is another (Gothic, crawled in Latin
                    # letters), the language is left to Google's text. What Google's data says of the
                    # language is kept (Old English is historical).
                    if tag in stated and script_of(one) not in stated[tag]:
                        continue
                    if tag in gf_text:
                        said = gf_text[tag][0]
                        one.name, one.autonym, one.speakers, one.historical = (said.name, said.autonym, said.speakers,
                                                                               said.historical)
                held = pieces[iso].setdefault(script_of(one), [])
                if not any(other.source == one.source for other in held):  # (a source's first file of a language and script)
                    held.append(one)

    # Keyboard layouts (KEYBOARD says how they rank): a language no source describes, or a script no
    # source gives a language in. Where Hyperglot or a declared source gives the language in the
    # layout's script, the layout is set aside; where counted sources do, its row takes their place.
    chosen, refused = read_keyboards(keyboards, scripts, problems) if keyboards else ({}, [])
    set_aside, replaced = [], []
    for (iso, script), (layout, units) in chosen.items():
        title = title_of_code(script)
        made = shaped(iso, script, "", "", units, [], [], KEYBOARD, True)
        if made is None:
            continue
        if iso in hyperglot or iso in taken:
            # (Hyperglot's rows first, then a declared source's, a second script of Hyperglot's included:
            # Manipuri in Meetei Mayek is SLDR's, and its layouts are set aside)
            others = hyperglot_written[iso] + [(one.name, written_in(one.base, scripts)) for one in taken.get(iso, ())]
            if script in [written for _, written in others]:
                set_aside.append((iso, script, layout))
                continue
            made.name = plain_name(others[0][0], title_of_code(others[0][1]), unicode_name(others[0][1])) if others else ""
            taken.setdefault(iso, []).append(made)
            continue
        found = Evidence(KEYBOARD, iso, script, units, None, 0)
        found.given = made
        held = pieces[iso].get(title)
        others = [one for written, ones in pieces[iso].items() if written != title for one in ones if one.name]
        if held:
            # (what the counted row's source says of the language is kept, as for An Crubadan's rows:
            # its name, autonym, speakers, and status; Google's data calls Mru's and Lushootseed's
            # orthographies historical)
            replaced.append((iso, title, [one.source for one in held]))
            made.name, made.autonym = plain_name(held[0].name, title, unicode_name(script)), held[0].autonym
            made.speakers, made.historical = held[0].speakers, held[0].historical
        elif others:
            made.name = plain_name(others[0].name, script_of(others[0]), unicode_name(others[0].script))
        pieces[iso][title] = [found]
    reinforced_rows = dependent_rows = 0
    for iso in sorted(pieces):
        made = []
        for found in sorted(pieces[iso].values(), key=lambda found: found[0].script):
            kept = independent(found)
            one = orthography_of(kept)
            if one is not None:
                made.append(one)
                reinforced_rows += len(kept) > 1
                dependent_rows += len(kept) < len(found)
        if made:
            taken[iso] = made

    texts, rows = [], []

    def text(items):
        joined = " ".join(items)
        if joined not in texts:
            texts.append(joined)
        return texts.index(joined)

    keys = [key for key, _, _ in SOURCE_ROWS]
    unnamed = []
    for iso in sorted(taken):
        found = taken[iso]
        scripts_seen = set()
        for one in sorted(found, key=lambda one: one.script):
            script = title_of_code(one.script)  # (Unicode's name where no other is known: Tai Yo)
            if script in scripts_seen:
                continue
            scripts_seen.add(script)
            row = by_iso.get(iso)
            name = one.name or (row["Name"] if row is not None else "")
            if not name:
                unnamed.append(iso)
                name = iso
            status = "h" if one.historical else "c" if row is not None and row["Family_ID"] == ARTIFICIAL else ""
            rows.append([iso, name, one.autonym if one.autonym != name else "", script, status, one.validity,
                         one.speakers, text(one.base), text(one.auxiliary), one.marks, keys.index(one.source),
                         "k" if one.source == KEYBOARD else "i" if one.source in INFERRED else "d"])
            if one.rests and one.source != KEYBOARD:  # (an inferred row: every source it rests on, and the letters each counted)
                rows[-1].append([[keys.index(source), size] for source, size in one.rests])
            rows_by_source[one.source] = rows_by_source.get(one.source, 0) + 1
    data = collections.OrderedDict((
        ("source", "The languages Hyperglot does not describe, and scripts it does not give its languages in, "
                   "from %s: see language_orthographies_LICENSE"
                   % "; ".join("%s (%s)" % (title, license_) for _, title, license_ in SOURCE_ROWS)),
        ("columns", ["iso", "name", "autonym", "script", "status", "validity", "speakers", "base", "auxiliary",
                     "marks", "source", "evidence", "rests"]),
        ("status", {"l": "living", "h": "historical", "c": "constructed", "": "not given"}),
        ("evidence", {"d": "declared", "i": "inferred", "k": "keyboard"}),
        # [key, what a tooltip says, license, what its count counts ("text", "words", or "")]
        ("sources", [list(row) + [COUNTED_AS.get(row[0], "")] for row in SOURCE_ROWS]),
        ("rule", "inferred from a counted text: letters only, of the text's main script, each at least 1 in "
                 "%d of the letters and in %d word forms (or trigrams, or places) or more, from %d letters on; "
                 "with several independent sources, a letter one source keeps and another has, or one that "
                 "makes 1 letter in %d alone"
                 % (round(1 / INFERRED_SHARE), INFERRED_TIMES, INFERRED_LETTERS,
                    round(1 / (INFERRED_SHARE * REINFORCED_ALONE)))),
        ("keyboard_rule", "from a keyboard layout: the letters and marks of the script its keys and rules type, in "
                          "NFC (in Latin, a to z and their capitals with what it adds), from %d on, of which %d or "
                          "more an English keyboard does not type, and %d or fewer letters of another script; one "
                          "layout per language and script, alone"
                          % (KEYBOARD_FLOOR, KEYBOARD_OWN, KEYBOARD_FOREIGN)),
        ("orthographies", rows),
        ("texts", texts),
    ))
    # What is known and cannot be checked. Scripts: those of Unicode (Scripts.txt) no orthography of
    # either file is written in. Languages: a script is recorded for some that no source gives
    # characters for, by CLDR (the scripts of supplementalData's languageData, and the likely script)
    # and by Google's data (a language file with a script and nothing to count): kept by ISO 639-3
    # code, so Font Check can say what such a language is written in.
    with open(LANGUAGES_FILE, encoding="utf-8") as handle:
        written = set(row[3] for row in json.load(handle)["orthographies"]) | set(row[3] for row in rows)
    unicode_scripts = sorted(set(script for _, _, script in counter.ranges) - set(("Common", "Inherited")))
    # (each Unicode script by its own code, PropertyValueAliases.txt's: a script whose name Google's
    # data gives otherwise, Warang Citi's Varang Kshiti, was found by neither name before)
    not_covered = [script.replace("_", " ") for script in unicode_scripts
                   if title_of_code(counter.code_of_script(script)) not in written]
    root = ElementTree.fromstring(archive.read("common/supplemental/supplementalData.xml"))
    for one in root.iter("language"):
        if one.get("type") and one.get("scripts"):
            for code in one.get("scripts").split():
                if code not in said_scripts.setdefault(one.get("type"), []):
                    said_scripts[one.get("type")].append(code)
    for tag, code in codes.likely.items():
        if code not in said_scripts.setdefault(tag, []):
            said_scripts[tag].append(code)
    by_script = collections.defaultdict(set)
    for tag in sorted(said_scripts):
        for iso in codes.isos(tag):
            if iso not in hyperglot and iso not in taken:
                for code in said_scripts[tag]:
                    if code not in ("Zyyy", "Zxxx", "Zzzz", "Brai"):  # (no script, unwritten, unknown; Braille is no orthography)
                        by_script[title_of_code(code)].add(iso)
    data["scripts"] = collections.OrderedDict((
        ("unicode", "Unicode %s (Scripts.txt)" % UNICODE_VERSION), ("known", len(unicode_scripts)),
        ("not_covered", not_covered),
        # script's name: the ISO 639-3 codes of languages no source gives characters for that a source says are written in it
        ("of_other_languages", collections.OrderedDict((script, " ".join(sorted(by_script[script])))
                                                       for script in sorted(by_script))),
    ))
    summary = collections.OrderedDict()
    for key, _, _ in SOURCE_ROWS:
        summary[key] = (len(set(row[0] for row in rows if keys[row[10]] == key)), rows_by_source.get(key, 0))
    summary["(resting on two or more independent sources)"] = (
        len(set(row[0] for row in rows if len(row) > 12 and len(row[12]) > 1)), reinforced_rows)
    summary["(a source set aside as the same text as another)"] = (0, dependent_rows)
    summary["(a layout set aside: a declared row in its script)"] = (len(set(iso for iso, _, _ in set_aside)),
                                                                     len(set_aside))
    summary["(a counted row a layout took the place of)"] = (len(set(iso for iso, _, _ in replaced)), len(replaced))
    for iso, title, sources in replaced:
        problems.append("keyboard: %s in %s rests on its layout, not on %s" % (iso, title, ", ".join(sources)))
    for layout, iso, script, units, own, foreign in refused:
        if units < KEYBOARD_FLOOR or own < KEYBOARD_OWN:
            problems.append("keyboard %s (%s, %s): %d letters and marks of the script, %d an English keyboard lacks: "
                            "under the floor" % (layout, iso, script, units, own))
        else:
            problems.append("keyboard %s (%s, %s): %d letters of other scripts (%s): unfinished" % (
                layout, iso, script, len(foreign),
                ", ".join("%s %s" % (code, "".join(ch for ch in foreign if scripts.code_of(ch) == code))
                          for code in sorted(set(scripts.code_of(ch) for ch in foreign)))))
    if no_language:
        problems.append("subtags that name no language Glottolog knows: %s" % " ".join(sorted(no_language)))
    return data, summary, problems, unnamed


def layout_header(path):
    """The comment lines a layout file opens with (its license header), without the slashes."""
    lines = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.startswith("//"):
                break
            lines.append(line[2:].strip())
    return lines


def license_notice(paths, texts, glottolog_folder, keyboards=None):
    def member(archive_name, inner):
        with tarfile.open(paths[archive_name], "r:gz") as archive:
            return archive.extractfile(inner).read().decode("utf-8").replace("\r\n", "\n").strip() + "\n"

    def zipped(archive_name, inner):
        with zipfile.ZipFile(texts[archive_name]) as archive:
            return archive.read(inner).decode("utf-8").replace("\r\n", "\n").strip() + "\n"

    code, capture, _, _ = CRUBADAN_ARCHIVES[0]
    _, families = glottolog_tables(glottolog_folder)
    with open(families.download(glottolog_folder)["LICENSE"], encoding="utf-8") as handle:
        cc_by = handle.read().replace("\r\n", "\n").strip() + "\n"  # (the license's text, as Glottolog ships it)

    with open(paths["unicode-license.txt"], encoding="utf-8") as handle:
        unicode_license = handle.read().replace("\r\n", "\n").strip() + "\n"
    rule = "-" * 80
    lines = [
        "language_orthographies.json holds the characters languages are written with, for the",
        "languages Hyperglot (language_coverage.json) does not describe. checks/train/orthographies.py",
        "derives it from the seven sources below, each at a pinned version, and each row of the file",
        "names its sources; Glottolog (8) gives names, a status, and which codes name a language.",
        "None of them endorses this file or FreeLab.",
        "",
        "1. Google Fonts' language data (https://github.com/googlefonts/lang, release v%s)," % GF_TAG,
        "   Copyright Google LLC and its contributors, licensed under the Apache License, Version 2.0.",
        "   Changes made: each language's exemplar characters (base, auxiliary, marks), name, autonym,",
        "   script, population, and historical flag are kept in a compact form; for a language with a",
        "   sample text and no exemplar characters, the letters of the text are counted and those",
        "   frequent enough are kept (marked as inferred).",
        "",
        "2. Unicode CLDR %s (https://cldr.unicode.org), Copyright Unicode, Inc., licensed under the" % CLDR_VERSION,
        "   Unicode License V3. Changes made: each locale's main and auxiliary exemplar characters,",
        "   with the capital of each small letter added, the language's English name and its name in",
        "   its own locale; CLDR's language alias and likely-script tables give codes and scripts.",
        "",
        "3. SIL's Locale Data Repository (https://github.com/silnrsi/sldr, tag %s)," % SLDR_TAG,
        "   Copyright (c) 2014-2023 SIL International, licensed under the MIT License. Changes made:",
        "   as for CLDR; the exemplars SLDR marks as generated by its tools are marked as inferred,",
        "   and those it marks as suspect are left out.",
        "",
        "4. Unilex (https://github.com/unicode-org/unilex, commit %s)," % UNILEX_COMMIT,
        "   Copyright Unicode, Inc., licensed under the Unicode License V3 (its frequency files carry",
        "   SPDX-License-Identifier: Unicode-DFS-2016). Changes made: the letters of each language's",
        "   word forms are counted, weighted by the forms' frequencies, and those frequent enough are",
        "   kept (marked as inferred); no word is kept.",
        "",
        "5. %s (http://crubadan.org/), edited by Kevin Scannell (Saint Louis University). Its" % CRUBADAN,
        "   site no longer answers; two copies of its data are used.",
        "   a. The archives it published per writing system, each with its notice (below): \"This",
        "      %s language dataset is licensed under a Creative Commons Attribution 4.0" % CRUBADAN[3:],
        "      International License.\" The site said the same of itself (\"%s edited by" % CRUBADAN,
        "      Scannell, Kevin is licensed under a Creative Commons Attribution 4.0 International",
        "      License\", as captured on 2021-03-01:",
        "      http://web.archive.org/web/20210301152549/http://crubadan.org/). Taken from the Internet",
        "      Archive's Wayback Machine, the %d archives it captured:" % len(CRUBADAN_ARCHIVES),
    ] + ["      %s" % (WAYBACK % (capture_, folder, code_)) for code_, capture_, folder, _ in CRUBADAN_ARCHIVES] + [
        "      Changes made: the letters of each language's word forms (its word frequency list) are",
        "      counted, weighted by the forms' frequencies, and those frequent enough are kept (marked",
        "      as inferred); no word is kept.",
        "   b. Its character trigram counts of 11 April 2010 for 449 writing systems, Copyright 2010",
        "      Kevin P. Scannell, licensed under the GNU General Public License, version 3 or (at your",
        "      option) any later version, as NLTK distributes them (the \"crubadan\" package of",
        "      https://github.com/nltk/nltk_data, commit %s)." % NLTK_CRUBADAN_COMMIT,
        "      Changes made: the middle character of each trigram is counted, and the letters frequent",
        "      enough are kept (marked as inferred); no trigram is kept. The General Public License,",
        "      version 3, is the LICENSE file of FreeLab's repository.",
        "   The project asks that this paper be cited: Kevin P. Scannell, \"The %s Project:" % CRUBADAN[3:],
        "   Corpus building for under-resourced languages\", in Building and Exploring Web Corpora:",
        "   Proceedings of the 3rd Web as Corpus Workshop (WAC3), Louvain-la-Neuve, 2007.",
        "",
        "6. The Universal Declaration of Human Rights, in the translations the \"UDHR in Unicode\"",
        "   project (http://unicode.org/udhr/) had gathered by 2012, as NLTK distributes them (the",
        "   \"udhr2\" package of https://github.com/nltk/nltk_data, commit",
        "   %s). NLTK's index entry for the package at that" % NLTK_UDHR2_COMMIT,
        "   commit (packages/corpora/udhr2.xml) reads:",
        "      %s" % UDHR2_INDEX.replace('" webpage', '"\n      webpage').replace('" license', '"\n      license'),
        "   The archive holds the texts alone, with no readme or license file of its own. Changes",
        "   made: the letters of each language's text are counted, and those frequent enough are kept",
        "   (marked as inferred); no text is kept.",
        "",
    ] + keyboard_notice(keyboards) + [
        "8. Glottolog %s (https://glottolog.org), by Harald Hammarstr\N{LATIN SMALL LETTER O WITH DIAERESIS}m, "
        "Robert Forkel, Martin" % families.GLOTTOLOG_VERSION,
        "   Haspelmath, and Sebastian Bank (Leipzig: Max Planck Institute for Evolutionary",
        "   Anthropology, 2026), as published in CLDF by https://github.com/glottolog/glottolog-cldf",
        "   (release v%s, commit %s)," % (families.GLOTTOLOG_VERSION, families.COMMIT),
        "   licensed under the Creative Commons Attribution 4.0 International license (below). Cite as:",
    ] + textwrap.wrap(families.CITATION, 92, initial_indent="   ", subsequent_indent="   ") + [
        "   Changes made: of its table of languoids (languages.csv) and classification",
        "   (classification.nex), the ISO 639-3 codes that name a language (a code a source gives that",
        "   Glottolog has not is left out), the English name of a language no source names, the",
        "   constructed status of a language in its Artificial Language family, and the members of a",
        "   language Hyperglot describes through them (Akan: no row of its own). No other part of",
        "   Glottolog is included, and Glottolog does not endorse this file or FreeLab.",
        "",
        "Where two or more of the inferred sources describe a language in the same script, a letter is",
        "kept when one of them keeps it and another has it, and each such row names every source it",
        "rests on; a declared orthography (sources 1 to 3) is never mixed with another, nor is a",
        "keyboard layout's row (source 7) mixed with any.",
        "",
        "The Unicode Character Database %s (Scripts.txt, ScriptExtensions.txt, PropertyValueAliases.txt," % UNICODE_VERSION,
        "UnicodeData.txt; Unicode License V3) tells which script a counted or typed letter belongs to.",
        "The licenses follow.",
        "",
        rule, "", "Apache License, Version 2.0 (Google Fonts' language data)", "",
        member("lang-%s.tar.gz" % GF_TAG, "%s/LICENSE.txt" % GF_ROOT),
        rule, "", "Unicode License V3 (Unicode CLDR, Unilex, the Unicode Character Database)", "",
        unicode_license,
        rule, "", "MIT License (SIL's Locale Data Repository)", "",
        member("sldr-%s.tar.gz" % SLDR_TAG, "%s/LICENSE" % SLDR_ROOT),
        rule, "", "The notice of %s's archives (the LICENSE file of each)" % CRUBADAN, "",
        zipped("crubadan-%s-%s.zip" % (code, capture), "LICENSE"),
        rule, "", "Creative Commons Attribution 4.0 International (%s's archives and Glottolog; the text as "
                  "Glottolog's repository ships it)" % CRUBADAN, "",
        cc_by,
    ]
    if keyboards:
        with open(keyboards[LANGUAGE_TOOLS_LICENSE[0]], encoding="utf-8") as handle:
            lines += [rule, "", "Apache License, Version 2.0 (Language Tools: its LICENSE file)", "",
                      handle.read().replace("\r\n", "\n").strip() + "\n"]
    return "\n".join(lines)


def keyboard_notice(keyboards):
    """The license notice's paragraph on the keyboard layouts (none without them)."""
    if not keyboards:
        return []
    headed = [name for name, _, _, _ in KEYBOARDS
              if "Licensed under the Apache License, Version 2.0 (the \"License\");"
              in " ".join(layout_header(keyboards["%s.js" % name]))]
    bare = [name for name, _, _, _ in KEYBOARDS if name not in headed]
    return [
        "7. Language Tools (https://languagetools-153419.appspot.com/), keyboard layouts by Craig",
        "   Cornelius and contributors, with Translation Commons: the layout files of its source",
        "   repository, https://github.com/sven-oly/LanguageTools, branch p3_version, commit",
        "   %s, whose LICENSE file is the Apache License," % LANGUAGE_TOOLS_COMMIT,
        "   Version 2.0 (below).",
        "   %d of the %d layout files read open with this header (%s.js):" % (
            len(headed), len(KEYBOARDS), headed[0]),
    ] + [("      %s" % line).rstrip() for line in layout_header(keyboards["%s.js" % headed[0]])] + [
        "   The other %d carry no license line of their own, and the repository's LICENSE covers them:" % len(bare),
    ] + textwrap.wrap(", ".join("%s.js" % name for name in bare) + ".", 95, initial_indent="   ",
                      subsequent_indent="   ") + [
        "   Changes made: the letters and combining marks of the script that each layout's keys and",
        "   rules type are kept, each once (in Latin, with the letters a to z and their capitals);",
        "   one layout per language and script, marked as a keyboard layout; no layout, key map, or",
        "   rule is kept. None of the repository's fonts is used.",
        "",
    ]


# ---------------------------------------------------------------------------
# The characters the list font must draw
# ---------------------------------------------------------------------------

def ranges_of(codes):
    """Code points as hexadecimal ranges, as character_sets.json writes them."""
    parts, codes = [], sorted(codes)
    at = 0
    while at < len(codes):
        end = at
        while end + 1 < len(codes) and codes[end + 1] == codes[end] + 1:
            end += 1
        parts.append("%04X" % codes[at] if end == at else "%04X-%04X" % (codes[at], codes[end]))
        at = end + 1
    return " ".join(parts)


BLOCK_FONT_LIMIT = 256  # a Unicode block's set of more characters is not drawn whole by the bundled font
SCRIPT_FONT_LIMIT = 300  # a script's set is drawn whole when its own characters number at most this


def font_characters():
    """What Font Check's lists and tooltips show, from the data files as they are on disk: the
    code points of the names (languages' names and autonyms, script, group, and family headings), of
    the other names a tooltip may show, of the orthographies (base, auxiliary, marks), and of the
    character sets."""
    def load(path):
        if not os.path.isfile(path):
            return None
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    names, others, orthographies, sets = set(), set(), set(), set()
    for path in (LANGUAGES_FILE, OUT_FILE):
        data = load(path)
        for row in (data or {}).get("orthographies", ()):
            for value in row[1:4]:
                names.update(ord(ch) for ch in value)
            for index in row[7:9]:
                orthographies.update(ord(ch) for ch in data["texts"][index] if ch != " ")
            orthographies.update(ord(ch) for ch in row[9])
        for row in (data or {}).get("sources", ()):
            names.update(ord(ch) for ch in row[1])
        for name in list((data or {}).get("scripts", {}).get("not_covered", ())) + list(
                (data or {}).get("scripts", {}).get("of_other_languages", ())):
            names.update(ord(ch) for ch in name)  # (the scripts not yet covered are listed too)
    families = load(FAMILIES_FILE) or {}
    for name, _ in families.get("nodes", ()):
        names.update(ord(ch) for ch in name)
    for row in families.get("unlisted", ()):  # (the languages not yet covered are listed under their families)
        names.update(ord(ch) for ch in row[1])
    for found in families.get("aliases", {}).values():
        for name in found:
            others.update(ord(ch) for ch in name)
    def codes_of(ranges):
        found = set()
        for part in ranges.split():
            low, _, high = part.partition("-")
            found.update(range(int(low, 16), int(high or low, 16) + 1))
        return found

    data = load(SETS_FILE) or {}
    for group in data.get("groups", ()):
        names.update(ord(ch) for ch in group)
    # The font cannot hold all of Unicode (65,535 glyphs at most), so the sets are bounded: a Unicode
    # block's set of more than BLOCK_FONT_LIMIT characters is left out, and so is a script's set whose
    # own characters number more than SCRIPT_FONT_LIMIT (Han, Hangul, Tangut, the hieroglyphs,
    # cuneiform: what the orthographies use of them is in already). Their names are drawn all the same;
    # the pictures of their missing characters fall back to the system's fonts.
    blocks_out, scripts_out, of_scripts = [], [], set()
    for row in data.get("sets", ()):
        names.update(ord(ch) for ch in row[1])
        codes = codes_of(row[4])
        if row[0].startswith("block-") and len(codes) > BLOCK_FONT_LIMIT:
            blocks_out.append(row[1])
            continue
        sets.update(codes)
        for sequence in row[5].split():
            sets.update(int(code, 16) for code in sequence.split("+"))
    scripts = data.get("scripts") or {}
    names.update(ord(ch) for ch in scripts.get("group", ""))
    for row in scripts.get("rows", ()):
        names.update(ord(ch) for ch in row[0])
        own = codes_of(row[1])
        if len(own) > SCRIPT_FONT_LIMIT:
            scripts_out.append(row[0])
            continue
        of_scripts.update(own | codes_of(row[2]))
    sets.update(of_scripts)
    # What the lists add of their own: digits, the punctuation of labels and tooltips, the dotted circle
    # a mark is shown on, and the ellipsis a cut text ends with.
    names.update(range(0x20, 0x7F))
    names.update((0x25CC, 0x2026, 0x00A0))
    everything = names | others | orthographies | sets
    return collections.OrderedDict((
        ("about", "The characters Font Check's lists and tooltips show, for checks/train/language_font.py: "
                  "hexadecimal code points and ranges. names: the languages' names and autonyms and the "
                  "headings (always shown); other_names: Glottolog's other names (a tooltip shows the one a "
                  "search found); orthographies: base, auxiliary, and mark characters; sets: the character sets' "
                  "and the scripts' own and shared characters, but those of a Unicode block of more than %d "
                  "characters and of a script of more than %d (left_out names them)."
                  % (BLOCK_FONT_LIMIT, SCRIPT_FONT_LIMIT)),
        ("counts", collections.OrderedDict((("all", len(everything)), ("names", len(names)),
                                            ("other_names", len(others)), ("orthographies", len(orthographies)),
                                            ("sets", len(sets)), ("of_scripts", len(of_scripts))))),
        ("left_out", collections.OrderedDict((("blocks", blocks_out), ("scripts", scripts_out)))),
        ("names", ranges_of(names)), ("other_names", ranges_of(others)),
        ("orthographies", ranges_of(orthographies)), ("sets", ranges_of(sets)),
    ))


def write_json(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--download", help="a folder to download the pinned sources into")
    parser.add_argument("--glottolog", help="the folder of Glottolog's tables (families.py's; default: the "
                                            "folder \"glottolog\" beside --download)")
    parser.add_argument("--texts", help="the folder of the counted texts fetched one file at a time: An "
                                        "Crubadan's archives and NLTK's package of it (default: the folder "
                                        "\"crubadan\" beside --download)")
    parser.add_argument("--keyboards", help="the folder of Language Tools' layout files, fetched one at a time "
                                            "(default: the folder \"keyboards\" beside --download)")
    parser.add_argument("--characters", action="store_true",
                        help="write only font_characters.json, from the data files as they are")
    parser.add_argument("--out", default=OUT_FILE)
    parser.add_argument("--license-out", default=LICENSE_FILE)
    parser.add_argument("--characters-out", default=CHARACTERS_FILE)
    args = parser.parse_args()
    if not args.characters:
        if not args.download:
            parser.error("give --download or --characters")
        paths = download(args.download)
        beside = os.path.dirname(os.path.abspath(args.download))
        glottolog = args.glottolog or os.path.join(beside, "glottolog")
        texts = download(args.texts or os.path.join(beside, "crubadan"), TEXT_SOURCES, TEXT_PAUSE)
        keyboards = download(args.keyboards or os.path.join(beside, "keyboards"), KEYBOARD_SOURCES, KEYBOARD_PAUSE)
        data, summary, problems, unnamed = build(paths, glottolog, texts, keyboards)
        write_json(args.out, data)
        with open(args.license_out, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(license_notice(paths, texts, glottolog, keyboards))
        for line in problems:
            print("skipped: %s" % line, file=sys.stderr)
        rows = data["orthographies"]
        print("%d orthographies of %d languages written to %s (%d bytes)" % (
            len(rows), len(set(row[0] for row in rows)), os.path.basename(args.out), os.path.getsize(args.out)))
        for key, (languages, count) in summary.items():
            print("  %-17s %5d languages, %5d orthographies" % (key, languages, count))
        if unnamed:
            print("  without a name (their code stands in): %s" % " ".join(unnamed))
    characters = font_characters()
    write_json(args.characters_out, characters)
    print("%s: %s" % (os.path.basename(args.characters_out),
                      ", ".join("%s %d" % (key, value) for key, value in characters["counts"].items())))


if __name__ == "__main__":
    main()
