# -*- coding: utf-8 -*-
"""The check for fonts FontLab 7.2 crashes on (a GPOS single adjustment of format 2 with no values), the fixed
copy opened instead, and the question asked first, on tiny fonts built here (fontbytes). Python 2.7 and 3."""

from __future__ import absolute_import, division, print_function

import os
import shutil
import struct
import sys
import tempfile
import time
import unittest

os.environ["FREELAB_NO_AUTOSTART"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, os.pardir, "kerning"))
import fontbytes as fb  # noqa: E402
import freelab_auto_kerning as ak  # noqa: E402

EMPTY = fb.single(2, 0, 0)  # the crasher: format 2, no values
EMPTY_FOUR = fb.single(2, 4, 0, glyphs=(1, 2, 3, 4, 5, 6, 7), ranged=True)


def crasher_gpos():
    """Lookup 0 a pair adjustment; lookup 1 type 1 with a format 1, an empty format 2, and a full format 2;
    lookup 2 an extension of an empty format 2; lookup 3 an extension of a pair adjustment."""
    return fb.gpos([
        fb.lookup(2, [fb.pair()]),
        fb.lookup(1, [fb.single(1, 4), EMPTY, fb.single(2, 4, 3)]),
        fb.lookup(9, [fb.extension(EMPTY_FOUR)]),
        fb.lookup(9, [fb.extension(fb.pair(), kind=2)]),
    ])


def clean_gpos():
    return fb.gpos([fb.lookup(1, [fb.single(1, 0), fb.single(2, 0, 3), fb.single(2, 4, 1)]),
                    fb.lookup(9, [fb.extension(fb.single(2, 5, 2))])])


def font(gpos=None):
    tables = {b"head": fb.head(), b"name": b"\0\0\0\0\0\x06" + b"x" * 7}
    if gpos is not None:
        tables[b"GPOS"] = gpos
    return tables


def shared_gpos(heads, repeats, tails=(), count=4000):
    """A GPOS of these lookups (each lookup's bytes), then repeats lookups that are one lookup of count format 1
    subtables over glyphs, all one subtable (repeats x count steps of the check, in some 8 KB), then tails."""
    shared = struct.pack(">HHH", 1, 0, count) + struct.pack(">H", 6 + 2 * count) * count + fb.single(1, 0)
    total = len(heads) + repeats + len(tails)
    listing = 2 + 2 * total
    offsets, body = [], b""
    for item in heads:
        offsets.append(listing + len(body))
        body += item
    offsets += [listing + len(body)] * repeats
    body += shared
    for item in tails:
        offsets.append(listing + len(body))
        body += item
    return (struct.pack(">HHHHH", 1, 0, 10, 12, 14) + struct.pack(">HH", 0, 0) + struct.pack(">H", total) +
            b"".join(struct.pack(">H", at) for at in offsets) + body)


def identity_brotli():
    """A _brotli_decompress for fontbytes' WOFF2, whose stream is not compressed."""
    return lambda data, limit: data


class FakeBrotli(object):
    """What the check uses of brotli 1.2 (Decompressor().process(data, output_buffer_limit=...)), for sys.modules:
    process gives a bomb's stream (zeros without end), cut at the limit; its decompress never bounds what it gives.
    bounded=False: a brotli older than 1.2, whose process takes no limit."""

    def __init__(self, bounded=True):
        self.limits = []
        fake = self

        class Decompressor(object):
            if bounded:
                def process(self, data, output_buffer_limit=None):
                    if output_buffer_limit is None:
                        raise AssertionError("decompressed without a bound")
                    if not data:
                        return b""
                    fake.limits.append(output_buffer_limit)
                    return b"\0" * output_buffer_limit
            else:
                def process(self, data):
                    raise AssertionError("decompressed without a bound")
        self.Decompressor = Decompressor

    def decompress(self, data):
        raise AssertionError("decompressed without a bound")


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="freelab-crash-guard-")
        self.held = dict((name, getattr(ak, name)) for name in ("_brotli_decompress", "safe_copies_folder",
                                                                 "ask_open_fixed", "_qt", "empty_single_adjustments",
                                                                 "fixed_font_bytes"))
        self.modules = dict((name, sys.modules.get(name)) for name in ("brotli", "brotlicffi"))
        ak.safe_copies_folder = lambda: os.path.join(self.tmp, "copies")

    def tearDown(self):
        for name, value in self.held.items():
            setattr(ak, name, value)
        for name, module in self.modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name, data):
        path = os.path.join(self.tmp, name)
        with open(path, "wb") as handle:
            handle.write(data)
        return path

    def found(self, scan):
        return [(entry["font"], s["lookup"], s["subtable"], s["extension"], s["value_format"], s["glyphs"])
                for entry in scan["fonts"] for s in entry["subtables"]]


class DetectionTests(Case):
    def test_the_walker_finds_format_2_with_no_values_only(self):
        found = ak.empty_single_adjustments(crasher_gpos())
        self.assertEqual([(f["lookup"], f["subtable"], f["extension"], f["value_format"], f["glyphs"]) for f in found],
                         [(1, 1, False, 0, 3), (2, 0, True, 4, 7)])
        self.assertEqual(ak.empty_single_adjustments(clean_gpos()), [])

    def test_an_sfnt_and_its_summary(self):
        scan = ak.scan_font_file(self.write("Crash.ttf", fb.sfnt(font(crasher_gpos()))))
        self.assertEqual((scan["format"], scan["checked"], scan["count"]), ("sfnt", True, 2))
        self.assertEqual(self.found(scan), [(0, 1, 1, False, 0, 3), (0, 2, 0, True, 4, 7)])
        self.assertEqual(ak.crasher_summary(scan),
                         u"2 single adjustment subtables with no values (lookups 1 and 2)")
        one = ak.scan_font_file(self.write("One.otf", fb.sfnt(font(fb.gpos([fb.lookup(1, [EMPTY])])), b"OTTO")))
        self.assertEqual(ak.crasher_summary(one), u"1 single adjustment subtable with no values (lookup 0)")
        clean = ak.scan_font_file(self.write("Clean.ttf", fb.sfnt(font(clean_gpos()))))
        self.assertEqual((clean["checked"], clean["count"]), (True, 0))

    def test_every_font_of_a_collection(self):
        data = fb.collection([font(clean_gpos()), font(crasher_gpos()), font(fb.gpos([fb.lookup(1, [EMPTY])]))])
        scan = ak.scan_font_file(self.write("Family.ttc", data))
        self.assertEqual((scan["format"], scan["count"], [e["font"] for e in scan["fonts"]]), ("collection", 3, [1, 2]))
        self.assertEqual(ak.crasher_summary(scan), u"3 single adjustment subtables with no values "
                                                   u"(font 1: lookups 1 and 2; font 2: lookup 0)")

    def test_woff_and_woff2(self):
        scan = ak.scan_font_file(self.write("Crash.woff", fb.woff(font(crasher_gpos()))))
        self.assertEqual((scan["format"], scan["checked"], scan["count"]), ("woff", True, 2))
        path = self.write("Crash.woff2", fb.woff2(font(crasher_gpos())))
        ak._brotli_decompress = lambda: None
        scan = ak.scan_font_file(path)
        self.assertEqual((scan["checked"], scan["count"]), (False, 0))
        self.assertIn("brotli", scan["why_not"])
        ak._brotli_decompress = identity_brotli  # (fontbytes' stream is not compressed)
        self.assertEqual(ak.scan_font_file(path)["count"], 2)
        tables = [(b"head", fb.head()), (b"GPOS", clean_gpos()), (b"GPOS", crasher_gpos())]
        scan = ak.scan_font_file(self.write("Family.woff2", fb.woff2(tables, collection_of=[[0, 1], [0, 2]])))
        self.assertEqual([entry["font"] for entry in scan["fonts"]], [1])

    def test_sources_and_other_files_are_not_checked(self):
        for name, data in (("Font.vfc", b"\x00\x01\x02\x03"), ("Font.vfj", b'{"font": {}}'), ("Tiny.ttf", b"\x00")):
            scan = ak.scan_font_file(self.write(name, data))
            self.assertEqual((scan["format"], scan["checked"], scan["count"]), (None, False, 0), name)
        os.mkdir(os.path.join(self.tmp, "Font.ufo"))
        self.assertEqual(ak.scan_font_file(os.path.join(self.tmp, "Font.ufo"))["format"], None)
        self.assertEqual(ak.scan_font_file(os.path.join(self.tmp, "missing.otf"))["format"], None)
        cut = ak.scan_font_file(self.write("Cut.ttf", fb.sfnt(font(crasher_gpos()))[:60]))
        self.assertEqual(cut["checked"], False)
        self.assertIn("could not be read", cut["why_not"])

    def test_a_crasher_found_before_a_damaged_part_still_counts(self):
        # (Codex, 2026-11-19: an error part-way threw away what was found, and the file was opened as it is)
        broken = bytearray(fb.lookup(1, [fb.single(1, 0)]))
        struct.pack_into(">H", broken, 6, 0xFFF0)  # (its subtable past the table's end)
        gpos = fb.gpos([fb.lookup(1, [EMPTY]), bytes(broken), fb.lookup(1, [EMPTY])])
        scan = ak.scan_font_file(self.write("Half.ttf", fb.sfnt(font(gpos))))
        self.assertEqual((scan["checked"], scan["count"]), (False, 2), "the lookups after the damaged one are read")
        self.assertEqual([s["lookup"] for s in scan["fonts"][0]["subtables"]], [0, 2])
        data = bytearray(fb.collection([font(crasher_gpos()), font(clean_gpos())]))
        second = struct.unpack_from(">I", data, 16)[0]
        struct.pack_into(">H", data, second + 4, 0xFFFF)  # (font 1's table directory past the file's end)
        path = self.write("Half.ttc", bytes(data))
        scan = ak.scan_font_file(path)
        self.assertEqual((scan["checked"], scan["count"], [e["font"] for e in scan["fonts"]]), (False, 2, [0]))
        self.assertEqual(ak.write_safe_copy(path, scan, ak.safe_copy_path(path, scan, self.tmp)), 2,
                         "font 0 fixed; font 1 left as it is")

    def test_a_gpos_that_lists_its_data_over_and_over_is_read_only_so_far(self):
        # (Codex, 2026-11-19: lookups sharing one lookup of 65,535 subtables made 4 billion reads of 260 KB)
        count, lookups = 4000, 100
        sub = fb.single(1, 0)
        shared = struct.pack(">HHH", 1, 0, count) + struct.pack(">H", 6 + 2 * count) * count + sub
        first = fb.lookup(1, [EMPTY])
        listing = 2 + 2 * (lookups + 1)
        table = (struct.pack(">HHHHH", 1, 0, 10, 12, 14) + struct.pack(">HH", 0, 0) + struct.pack(">H", lookups + 1) +
                 struct.pack(">H", listing) + struct.pack(">H", listing + len(first)) * lookups + first + shared)
        started = time.time()
        scan = ak.scan_font_file(self.write("Loop.ttf", fb.sfnt(font(table))))
        self.assertLess(time.time() - started, 10)
        self.assertEqual((scan["checked"], scan["count"]), (False, 1), "the crasher before the limit is kept")
        self.assertIn("over and over", scan["why_not"])
        self.assertRaises(ak.FontFileLimit, ak.empty_single_adjustments, table)

    def test_lengths_past_the_file_are_refused_before_they_are_read(self):
        # (Codex, 2026-11-19: a collection of 4 billion fonts asked for 17 GB; a WOFF table could inflate past its length)
        scan = ak.scan_font_file(self.write("Huge.ttc", b"ttcf" + struct.pack(">HHI", 1, 0, 0xFFFFFFFF)))
        self.assertEqual((scan["format"], scan["checked"]), ("collection", False))
        self.assertIn("ends before", scan["why_not"])
        data = bytearray(fb.woff(font(crasher_gpos() + b"\0" * 5000)))
        self.assertEqual(bytes(data[44:48]), b"GPOS")
        struct.pack_into(">I", data, 44 + 12, 200)  # (its length said to be 200 bytes: the stream holds more)
        scan = ak.scan_font_file(self.write("Bomb.woff", bytes(data)))
        self.assertIn("longer than its directory says", scan["why_not"])
        struct.pack_into(">I", data, 44 + 12, ak.MAX_WOFF_TABLE + 1)
        self.assertIn("more than any font's", ak.scan_font_file(self.write("Bomb2.woff", bytes(data)))["why_not"])

    def test_a_copy_with_its_head_past_the_end_and_a_failed_write(self):
        data = bytearray(fb.sfnt(font(crasher_gpos())))
        entry = [12 + 16 * k for k in range(3) if bytes(data[12 + 16 * k:16 + 16 * k]) == b"head"][0]
        struct.pack_into(">I", data, entry + 8, len(data) + 100)  # (head past the file's end)
        path = self.write("NoHead.ttf", bytes(data))
        scan = ak.scan_font_file(path)
        self.assertEqual(scan["count"], 2, "head is not read by the check")
        target = os.path.join(self.tmp, "copies", "NoHead.ttf")
        self.assertEqual(ak.write_safe_copy(path, scan, target), 2, "fixed, head left as it is")
        real = os.rename

        def refused(*args):
            raise OSError("refused")
        ak.os.rename = refused
        try:
            self.assertRaises(OSError, ak.write_safe_copy, path, scan, os.path.join(self.tmp, "other", "NoHead.ttf"))
        finally:
            ak.os.rename = real
        self.assertEqual(os.listdir(os.path.join(self.tmp, "other")), [], "no .tmp left")


def subtable_count(data, li):
    """How many subtables lookup li of the sfnt's GPOS lists."""
    gpos = fb.tables_of(data)[b"GPOS"][0]
    listing = gpos + struct.unpack_from(">H", data, gpos + 8)[0]
    lookup = listing + struct.unpack_from(">H", data, listing + 2 + 2 * li)[0]
    return struct.unpack_from(">H", data, lookup + 4)[0]


class PartialCheckTests(Case):
    """A check that could not read the whole file says so, and costs no more than one budget (Codex, 2026-11-27):
    a coverage that cannot be read, a collection repeating one GPOS, a WOFF2 that inflates past its tables."""

    def test_a_coverage_that_cannot_be_read_leaves_the_check_unmade(self):
        lost_one = struct.pack(">HHH", 1, 0xFFF0, 4) + b"\0\0"  # (format 1, its coverage past the table's end)
        odd_one = struct.pack(">HHH", 1, 8, 4) + b"\0\0" + struct.pack(">HH", 3, 0)  # (a coverage of format 3)
        for sub in (lost_one, odd_one):
            scan = ak.scan_font_file(self.write("Lost.ttf", fb.sfnt(font(fb.gpos([fb.lookup(1, [sub, EMPTY])])))))
            self.assertEqual((scan["checked"], scan["count"]), (False, 1), "the subtable after it still read")
            self.assertIn(u"coverage", scan["why_not"])
        lost_two = struct.pack(">HHHH", 2, 0xFFF0, 0, 0)  # (format 2 with no values, its coverage past the end)
        path = self.write("LostTwo.ttf", fb.sfnt(font(fb.gpos([fb.lookup(1, [fb.single(1, 4), lost_two])]))))
        scan = ak.scan_font_file(path)
        self.assertEqual((scan["checked"], self.found(scan)), (False, [(0, 0, 1, False, 0, None)]))
        target = os.path.join(self.tmp, "copy.ttf")
        self.assertEqual(ak.write_safe_copy(path, scan, target), 1)
        with open(target, "rb") as handle:
            self.assertEqual(subtable_count(handle.read(), 0), 1, "taken out, never made format 1 over that coverage")
        again = ak.scan_font_file(target)
        self.assertEqual((again["checked"], again["count"]), (True, 0))

    def test_a_collection_has_one_budget_and_reads_a_shared_gpos_once(self):
        reads = []
        real = ak.empty_single_adjustments

        def counted(gpos, *args, **kwargs):
            reads.append(len(gpos))
            return real(gpos, *args, **kwargs)
        ak.empty_single_adjustments = counted
        shared = font(shared_gpos([fb.lookup(1, [EMPTY])], 30))  # (120,000 steps)
        scan = ak.scan_font_file(self.write("Shared.ttc", fb.collection([shared, shared, shared])))
        self.assertEqual((scan["checked"], scan["count"], [e["font"] for e in scan["fonts"]]), (True, 3, [0, 1, 2]))
        self.assertEqual(len(reads), 1, "one GPOS for three fonts: read once")
        two = fb.collection([font(shared_gpos([fb.lookup(1, [EMPTY])], 30)),
                             font(shared_gpos([fb.lookup(1, [EMPTY])], 31))])
        scan = ak.scan_font_file(self.write("Two.ttc", two))
        self.assertEqual((scan["checked"], scan["count"]), (False, 2), "240,000 steps in one file: past the budget")
        self.assertIn(u"over and over", scan["why_not"])

    def test_a_woff2_is_inflated_no_further_than_its_tables_say(self):
        path = self.write("Bomb.woff2", fb.woff2(font(crasher_gpos())))
        bomb = sys.modules["brotli"] = FakeBrotli()
        scan = ak.scan_font_file(path)
        self.assertEqual((scan["checked"], scan["count"]), (False, 0))
        self.assertIn(u"longer than its table directory says", scan["why_not"])
        stream = sum(len(data) for data in font(crasher_gpos()).values())
        self.assertEqual(bomb.limits, [stream + 1], "inflated to one byte past its tables at most")
        sys.modules["brotli"] = FakeBrotli(bounded=False)
        scan = ak.scan_font_file(path)
        self.assertEqual((scan["checked"], scan["count"]), (False, 0))
        self.assertIn(u"WOFF2 needs brotli 1.2 or later", scan["why_not"])
        directory = struct.pack(">B", 27) + fb.base128(ak.MAX_WOFF_TABLE + 1)  # (a GPOS said to be 256 MB and more)
        huge = struct.pack(">4s4sIHHIIHHIIIII", b"wOF2", b"\x00\x01\x00\x00", 52 + len(directory), 1, 0, 0, 4, 1, 0,
                           0, 0, 0, 0, 0) + directory + b"\0" * 4
        sys.modules["brotli"] = bomb
        scan = ak.scan_font_file(self.write("Huge.woff2", huge))
        self.assertIn(u"more than any font's", scan["why_not"])
        self.assertEqual(len(bomb.limits), 1, "refused before anything is inflated")

    def test_a_copy_that_still_holds_one_is_not_written(self):
        path = self.write("Crash.ttf", fb.sfnt(font(crasher_gpos())))
        scan = ak.scan_font_file(path)
        ak.fixed_font_bytes = lambda data, fmt: (data, 2)  # (a fix that fixed nothing)
        target = os.path.join(self.tmp, "copies", "Crash.ttf")
        with self.assertRaises(ak.FontFileError) as caught:
            ak.write_safe_copy(path, scan, target)
        self.assertIn(u"still holds 2", u"%s" % caught.exception)
        self.assertEqual(os.listdir(os.path.dirname(target)), [], "no copy, and no .tmp left")


def filtered_lookup(kind, subtables, mark_set):
    """A lookup with flag 0x10 (UseMarkFilteringSet): its mark filtering set follows the subtable offsets."""
    out = struct.pack(">HHH", kind, 0x10, len(subtables))
    at = 6 + 2 * len(subtables) + 2
    offsets, body = b"", b""
    for sub in subtables:
        offsets += struct.pack(">H", at + len(body))
        body += sub
    return out + offsets + struct.pack(">H", mark_set) + body


NO_GLYPH_2 = fb.single(2, 0, 0, glyphs=())  # format 2 with no values over no glyph
NO_GLYPH_1 = fb.single(1, 4, glyphs=())  # format 1 over no glyph (a fixed copy of a static instance, 2026-11-27)


class NoGlyphTests(Case):
    """A single adjustment over no glyph crashed FontLab 7.2 as format 1 too (2026-11-27: NotoSansJP[wght] at wght
    700, its copy fixed to format 1, crashed in the same function): it is found in either format, and the copy
    takes it out of its lookup (as FreeLab MCP's listener does)."""

    def gpos(self):
        return fb.gpos([fb.lookup(1, [fb.single(1, 4), NO_GLYPH_2, fb.single(2, 4, 3), NO_GLYPH_1]),
                        filtered_lookup(1, [NO_GLYPH_1, fb.single(1, 0), EMPTY], 7),
                        fb.lookup(9, [fb.extension(NO_GLYPH_2)])])

    def test_found_in_either_format(self):
        found = ak.empty_single_adjustments(self.gpos())
        self.assertEqual([(f["lookup"], f["subtable"], f["format"], f["glyphs"]) for f in found],
                         [(0, 1, 2, 0), (0, 3, 1, 0), (1, 0, 1, 0), (1, 2, 2, 3), (2, 0, 2, 0)])
        self.assertEqual(ak.empty_single_adjustments(fb.gpos([fb.lookup(1, [fb.single(1, 0)])])), [],
                         "format 1 over glyphs holds its value")

    def test_the_copy_takes_them_out(self):
        path = self.write("Static.ttf", fb.sfnt(font(self.gpos())))
        scan = ak.scan_font_file(path)
        self.assertEqual(scan["count"], 5)
        target = os.path.join(self.tmp, "copy.ttf")
        self.assertEqual(ak.write_safe_copy(path, scan, target), 5)
        with open(target, "rb") as handle:
            copy = handle.read()
        self.assertEqual(ak.scan_font_file(target)["count"], 0)
        gpos_at, gpos_length = fb.tables_of(copy)[b"GPOS"][:2]
        gpos = copy[gpos_at:gpos_at + gpos_length]
        listing = struct.unpack_from(">H", gpos, 8)[0]

        def subtables(li):
            lookup = listing + struct.unpack_from(">H", gpos, listing + 2 + 2 * li)[0]
            kind, flag, count = struct.unpack_from(">HHH", gpos, lookup)
            offsets = struct.unpack_from(">%dH" % count, gpos, lookup + 6)
            forms = [struct.unpack_from(">H", gpos, lookup + o)[0] for o in offsets]
            mark_set = struct.unpack_from(">H", gpos, lookup + 6 + 2 * count)[0] if flag & 0x10 else None
            return forms, mark_set
        self.assertEqual(subtables(0), ([1, 2], None), "the two over glyphs kept as they were")
        self.assertEqual(subtables(1), ([1, 1], 7), "the mark filtering set moved up with the offsets")
        self.assertEqual(subtables(2), ([], None), "a lookup of one such subtable is left with none")
        self.assertEqual(len(copy), os.path.getsize(path), "nothing moved")


class CopyTests(Case):
    def test_the_copy_holds_format_1_with_no_values_and_nothing_else_changed(self):
        original = fb.sfnt(font(crasher_gpos()))
        path = self.write("Crash[wght].ttf", original)
        scan = ak.scan_font_file(path)
        target = ak.safe_copy_path(path, scan, os.path.join(self.tmp, "copies"))
        self.assertEqual(os.path.basename(target), "Crash[wght].ttf")
        self.assertEqual(ak.write_safe_copy(path, scan, target), 2)
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(), original, "the original is only read")
        with open(target, "rb") as handle:
            copy = handle.read()
        self.assertEqual(len(copy), len(original))
        again = ak.scan_font_file(target)
        self.assertEqual((again["checked"], again["count"]), (True, 0))
        old, new = fb.tables_of(original), fb.tables_of(copy)
        for tag in old:
            a, b = original[old[tag][0]:old[tag][0] + old[tag][1]], copy[new[tag][0]:new[tag][0] + new[tag][1]]
            if tag == b"GPOS":
                self.assertEqual(len([k for k in range(len(a)) if a[k:k + 1] != b[k:k + 1]]), 3)
            elif tag == b"head":
                self.assertEqual((a[:8], a[12:]), (b[:8], b[12:]))
            else:
                self.assertEqual(a, b, tag)
        for entry in scan["fonts"]:
            for s in entry["subtables"]:
                self.assertEqual(struct.unpack_from(">HHH", copy, s["at"]),
                                 (1, struct.unpack_from(">H", original, s["at"] + 2)[0], 0))
        head_at = new[b"head"][0]
        zeroed = bytearray(copy)
        struct.pack_into(">I", zeroed, head_at + 8, 0)
        for tag, (offset, length, check) in new.items():
            self.assertEqual(fb.checksum(zeroed[offset:offset + length]), check, tag)
        self.assertEqual((0xB1B0AFBA - fb.checksum(zeroed)) & 0xFFFFFFFF, struct.unpack_from(">I", copy, head_at + 8)[0])

    def test_a_collection_and_a_woff(self):
        path = self.write("Family.ttc", fb.collection([font(clean_gpos()), font(crasher_gpos())]))
        scan = ak.scan_font_file(path)
        target = ak.safe_copy_path(path, scan, self.tmp)
        self.assertEqual(ak.write_safe_copy(path, scan, target), 2)
        self.assertEqual(ak.scan_font_file(target)["count"], 0)
        path = self.write("Web.woff", fb.woff(font(crasher_gpos()), b"OTTO"))
        scan = ak.scan_font_file(path)
        target = ak.safe_copy_path(path, scan, self.tmp)
        self.assertEqual(os.path.basename(target), "Web.otf")
        self.assertEqual(ak.write_safe_copy(path, scan, target), 2)
        again = ak.scan_font_file(target)
        self.assertEqual((again["format"], again["count"]), ("sfnt", 0))

    def test_a_woff2_is_not_copied(self):
        ak._brotli_decompress = identity_brotli
        path = self.write("Web.woff2", fb.woff2(font(crasher_gpos())))
        self.assertRaises(ak.FontFileError, ak.safe_copy_path, path, ak.scan_font_file(path), self.tmp)


class QuestionTests(Case):
    def setUp(self):
        Case.setUp(self)
        self.log = []
        self.Log = type("Log", (), {"add": lambda _self, text, level="info": self.log.append((level, text))})
        self.crasher = self.write("NotoSansJP[wght].ttf", fb.sfnt(font(crasher_gpos())))
        self.clean = self.write("Clean.ttf", fb.sfnt(font(clean_gpos())))

    def test_one_question_for_every_file_fontlab_crashes_on(self):
        asked = []
        other = self.write("Other.otf", fb.sfnt(font(fb.gpos([fb.lookup(1, [EMPTY])])), b"OTTO"))
        ak.ask_open_fixed = lambda parent, crashers: asked.append((parent, [p for p, s in crashers])) or True
        chosen = ak.crash_checked_paths([self.crasher, self.clean, other], "window", self.Log())
        self.assertEqual(asked, [("window", [self.crasher, other])], "one question for both")
        copies = os.path.join(self.tmp, "copies")
        self.assertEqual([(os.path.basename(c), p) for c, p in chosen],
                         [("NotoSansJP[wght].ttf", self.crasher), ("Clean.ttf", self.clean), ("Other.otf", other)])
        self.assertEqual([os.path.dirname(os.path.dirname(chosen[k][0])) for k in (0, 2)], [copies, copies],
                         "the copies in the temporary folder")
        self.assertEqual(chosen[1], (self.clean, self.clean), "a clean file opened as it is")
        self.assertEqual(ak.scan_font_file(chosen[0][0])["count"], 0)
        self.assertEqual([level for level, text in self.log], ["info", "info"])
        self.assertIn(u"<i>NotoSansJP[wght].ttf</i>: FontLab 7.2 crashes on it, so a fixed copy is opened instead",
                      self.log[0][1])
        self.assertIn(u"the file itself is not changed", self.log[0][1])
        self.assertIn(u"1 single adjustment subtable with no values (lookup 0) was made", self.log[1][1])

    def test_skipped_files_are_said_and_not_opened(self):
        ak.ask_open_fixed = lambda parent, crashers: False
        chosen = ak.crash_checked_paths([self.crasher, self.clean], None, self.Log())
        self.assertEqual(chosen, [(self.clean, self.clean)])
        self.assertEqual(self.log[0][0], "warning")
        self.assertIn(u"<i>NotoSansJP[wght].ttf</i> skipped: FontLab 7.2 crashes on it", self.log[0][1])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "copies")), "no copy written")

    def test_no_question_without_a_crasher_and_an_unchecked_file_is_said(self):
        ak.ask_open_fixed = lambda parent, crashers: self.fail("nothing to ask")
        ak._brotli_decompress = lambda: None
        web = self.write("Web.woff2", fb.woff2(font(crasher_gpos())))
        missing = os.path.join(self.tmp, "gone.vfc")
        chosen = ak.crash_checked_paths([self.clean, web, missing], None, self.Log())
        self.assertEqual(chosen, [(self.clean, self.clean), (web, web), (missing, missing)])
        self.assertEqual(self.log, [("warning", u"<i>Web.woff2</i> was not checked for the FontLab 7.2 crash (WOFF2 "
                                                u"needs brotli 1.2 or later, which FontLab's Python does not have): "
                                                u"opened as it is.")])

    def test_a_crasher_with_a_damaged_part_is_asked_about_and_the_rest_said(self):
        broken = bytearray(fb.lookup(1, [fb.single(1, 0)]))
        struct.pack_into(">H", broken, 6, 0xFFF0)
        half = self.write("Half.ttf", fb.sfnt(font(fb.gpos([fb.lookup(1, [EMPTY]), bytes(broken)]))))
        asked = []
        ak.ask_open_fixed = lambda parent, crashers: asked.append([p for p, s in crashers]) or True
        chosen = ak.crash_checked_paths([half], None, self.Log())
        self.assertEqual((asked, [p for c, p in chosen]), ([[half]], [half]), "asked about, and its copy opened")
        self.assertNotEqual(chosen[0][0], half)
        self.assertEqual([level for level, text in self.log], ["info", "warning"])
        self.assertIn(u"Part of <i>Half.ttf</i> was not checked", self.log[1][1])

    def test_a_copy_open_already_is_not_written_again(self):
        ak.ask_open_fixed = lambda parent, crashers: True
        first = ak.crash_checked_paths([self.crasher], None, self.Log())[0][0]
        with open(first, "wb") as handle:
            handle.write(b"as FontLab has it")
        # (live, 2026-11-19: the file added again was asked about again, and the log said a copy was opened)
        asked = []
        ak.ask_open_fixed = lambda parent, crashers: asked.append([p for p, s in crashers]) or True
        del self.log[:]
        again = ak.crash_checked_paths([self.crasher, self.clean], None, self.Log(),
                                       is_open=lambda path: path == first)
        self.assertEqual(again, [(first, self.crasher), (self.clean, self.clean)])
        self.assertEqual((asked, self.log), ([], []), "not asked about, and nothing said: the caller ticks it")
        with open(first, "rb") as handle:
            self.assertEqual(handle.read(), b"as FontLab has it")
        other = self.write("Other.otf", fb.sfnt(font(fb.gpos([fb.lookup(1, [EMPTY])])), b"OTTO"))
        ak.crash_checked_paths([self.crasher, other], None, self.Log(), is_open=lambda path: path == first)
        self.assertEqual(asked, [[other]], "asked only about the file whose copy is not open")

    def test_a_copy_that_cannot_be_made_opens_nothing(self):
        ak.ask_open_fixed = lambda parent, crashers: True
        ak._brotli_decompress = identity_brotli
        web = self.write("Web.woff2", fb.woff2(font(crasher_gpos())))
        self.assertEqual(ak.crash_checked_paths([web], None, self.Log()), [])
        self.assertEqual(self.log[0][0], "error")
        self.assertIn(u"convert it to TTF or OTF first", self.log[0][1])

    def message_boxes(self, boxes):
        """A QMessageBox for ak._qt, each one made added to boxes."""
        class Box(object):
            AcceptRole, RejectRole, Warning = "accept", "reject", "warning"

            def __init__(self, parent):
                self.parent, self.props, self.buttons, self.answer, self.default = parent, {}, {}, None, None
                boxes.append(self)

            def setProperty(self, name, value):
                self.props[name] = value

            def addButton(self, label, role):
                self.buttons[label] = role
                return label

            def setText(self, text):
                self.text = text

            def setDefaultButton(self, button):
                self.default = button

            def exec_(self):
                pass

            def clickedButton(self):
                return self.answer

            def buttonRole(self, button):
                return self.buttons[button]

            def __getattr__(self, name):
                return lambda *args: None
        ak._qt = lambda: (None, type("QtGui", (), {"QMessageBox": Box}))
        return Box

    def test_a_partial_check_is_said_before_the_choice_and_skip_is_the_default(self):
        # (Codex, 2026-11-27: the question called the copy fixed, and only the log said, once it was open, that part
        # of the file was not checked; a crasher past the budget was still in the copy)
        loop = self.write("Loop.ttf", fb.sfnt(font(shared_gpos([fb.lookup(1, [EMPTY])], 60, [fb.lookup(1, [EMPTY])]))))
        scan = ak.scan_font_file(loop)
        self.assertEqual((scan["checked"], scan["count"]), (False, 1), "the second one lies past the budget")
        boxes = []
        self.message_boxes(boxes)
        ak.ask_open_fixed("window", [(loop, scan)])
        text = boxes[-1].text
        self.assertIn(u"Part of Loop.ttf could not be checked (its tables could not be read: its GPOS lists more than "
                      u"200000", text)
        self.assertIn(u"FontLab may crash on its copy too, in what was not read. Save the work in your open fonts", text)
        self.assertLess(text.index(u"could not be checked"), text.index(u"A fixed copy"), "said before the copy")
        self.assertEqual(boxes[-1].default, u"Skip it", "skipping is the default")
        ak.ask_open_fixed("window", [(loop, scan), (self.crasher, ak.scan_font_file(self.crasher))])
        self.assertIn(u"Part of Loop.ttf could not be checked", boxes[-1].text)
        self.assertEqual(boxes[-1].default, u"Skip them")
        ak.ask_open_fixed("window", [(self.crasher, ak.scan_font_file(self.crasher))])
        self.assertEqual(boxes[-1].default, u"Open a fixed copy", "a file checked whole: the copy is the default")
        self.assertNotIn(u"could not be checked", boxes[-1].text)

    def test_the_question_is_freelabs_own_and_says_why(self):
        boxes = []
        Box = self.message_boxes(boxes)
        scan = ak.scan_font_file(self.crasher)
        self.assertFalse(ak.ask_open_fixed("window", [(self.crasher, scan)]), "Esc: skipped")
        box = boxes[-1]
        self.assertEqual((box.parent, box.props), ("window", {"mcpScriptWindow": True}))
        self.assertEqual(sorted(box.buttons), [u"Open a fixed copy", u"Skip it"])
        self.assertIn(u"FontLab 7.2 crashes on opening NotoSansJP[wght].ttf", box.text)
        self.assertIn(u"a crash loses the unsaved work in every open font", box.text)
        self.assertIn(u"2 single adjustment subtables with no values (lookups 1 and 2)", box.text)
        self.assertIn(u"Your file is not changed.", box.text)
        # (the subtables counted, not the files: live, one file of two read "such a subtable positions nothing")
        self.assertIn(u"such subtables position nothing, and each is made an empty one", box.text)
        one = self.write("One.otf", fb.sfnt(font(fb.gpos([fb.lookup(1, [EMPTY])])), b"OTTO"))
        ak.ask_open_fixed("window", [(one, ak.scan_font_file(one))])
        self.assertIn(u"such a subtable positions nothing, and it is made an empty one", boxes[-1].text)
        Box.exec_ = lambda self: setattr(self, "answer", u"Open fixed copies")
        self.assertTrue(ak.ask_open_fixed(None, [(self.crasher, scan), (self.crasher, scan)]))
        self.assertEqual(sorted(boxes[-1].buttons), [u"Open fixed copies", u"Skip them"])
        self.assertIn(u"these 2 files", boxes[-1].text)
        self.assertIn(u"Your files are not changed.", boxes[-1].text)


if __name__ == "__main__":
    unittest.main()
