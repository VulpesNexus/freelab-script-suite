# Removed from the font's source cache

*checks/train/language_font.py* keeps its pinned downloads in *%LOCALAPPDATA%\FreeLab\corpus\language-font-sources*, outside the repository. This is the manifest of what was deleted from that folder: each file's name, size, and SHA-256, and how to get it again.

## Sources that are no longer sources

GNU Unifont 17.0.05, from *https://ftp.gnu.org/gnu/unifont/unifont-17.0.05/*. It supplied sixteen characters until 2026-11-13, when Unicodia Funky's outlines replaced its pixel glyphs; no build reads it since. Deleted on 2026-11-13. The same files can be downloaded again from that address.

| File | Bytes | SHA-256 |
| --- | --- | --- |
| *unifont-17.0.05.otf* | 5,321,628 | `85701ab9b1e251ee16f4df00b13f22eac311d72b7dab427a7d975fe7f5064702` |
| *unifont_upper-17.0.05.otf* | 6,138,788 | `f4fd6d5d752726d384feef175bb780c9f29382cd4941c9e1e6990d7c3822a090` |
| *unifont-17.0.05.tar.gz* | 41,506,878 | `f287cffb26e22723aa36e6684869b0f3ff3bfb822c4b01008bd847911ec1b631` |
| *OFL-1.1.txt* (taken out of that archive) | 4,340 | `869692af094c57fb7258c57fe26820c759319603321d0ffeb278de3651763ded` |

## Intermediate files

The cache's *work* folder holds what a build makes on the way: one subset per source with its recipe, and each merged font before its line is set. The same pinned sources, fontTools 4.65.0, and uharfbuzz 0.57.0 make the same files again (`--stage subsets`, then `--stage merge`), as the second build of 2026-11-13 showed, so the folder is deleted after a build and its files are not listed one by one.

| Deleted | Files | Bytes | SHA-256 of the listing |
| --- | --- | --- | --- |
| 2026-11-13, after the build of the five fonts | 370 (180 subsets and 5 merged fonts, each with its recipe) | 25,055,273 | `29f6f96599858b968b1ce82e08bd6bab375aeb72462ff8e6b5f7e68c1522d339` |

The listing is one line per file, sorted by name: the name, the size in bytes, and the file's SHA-256, separated by one space and ended by a line feed, in UTF-8.
