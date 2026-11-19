# -*- coding: utf-8 -*-
"""Tiny font files built by hand for the tests (Python 2.7 and 3): just the tables the GPOS check reads, as
bytes, in an sfnt, a collection, a WOFF, or a WOFF2 (its "brotli" the identity, which the tests put in)."""

from __future__ import absolute_import, division, print_function

import struct
import zlib


def checksum(data):
    data = bytes(data) + b"\0" * (-len(data) % 4)
    return sum(struct.unpack(">%dI" % (len(data) // 4), data)) & 0xFFFFFFFF


def head():
    """A head table (54 bytes), its checkSumAdjustment 0."""
    return struct.pack(">IIIIHH8s8shhhhHHhhh", 0x00010000, 0x00010000, 0, 0x5F0F3CF5, 0, 1000, b"\0" * 8, b"\0" * 8,
                       0, 0, 100, 100, 0, 8, 2, 0, 0)


def coverage(glyphs, ranged=False):
    if ranged:  # (format 2: one range from the first glyph to the last)
        return struct.pack(">HHHHH", 2, 1, glyphs[0], glyphs[-1], 0)
    return struct.pack(">HH", 1, len(glyphs)) + b"".join(struct.pack(">H", g) for g in glyphs)


def _bits(value_format):
    return bin(value_format).count("1")


def single(form, value_format=0, count=0, glyphs=(3, 4, 5), ranged=False):
    """A single adjustment subtable: format 1 (one value record) or 2 (count value records), every value 0."""
    record = b"\0" * (2 * _bits(value_format))
    if form == 1:
        body = struct.pack(">HHH", 1, 6 + len(record), value_format) + record
    else:
        body = struct.pack(">HHHH", 2, 8 + count * len(record), value_format, count) + record * count
    return body + coverage(list(glyphs), ranged)


def pair():
    """A pair adjustment subtable of format 1 with no pair sets (another lookup type, never looked at)."""
    return struct.pack(">HHHHH", 1, 10, 4, 0, 0) + coverage([])


def extension(subtable, kind=1):
    return struct.pack(">HHI", 1, kind, 8) + subtable


def lookup(kind, subtables):
    out = struct.pack(">HHH", kind, 0, len(subtables))
    at = 6 + 2 * len(subtables)
    offsets, body = b"", b""
    for sub in subtables:
        offsets += struct.pack(">H", at + len(body))
        body += sub
    return out + offsets + body


def gpos(lookups):
    """A GPOS table: no scripts, no features, and these lookups (each lookup's bytes)."""
    listing = struct.pack(">H", len(lookups))
    at = 2 + 2 * len(lookups)
    offsets, body = b"", b""
    for item in lookups:
        offsets += struct.pack(">H", at + len(body))
        body += item
    return struct.pack(">HHHHH", 1, 0, 10, 12, 14) + struct.pack(">HH", 0, 0) + listing + offsets + body


def _directory_header(version, count):
    selector = 0
    while (1 << (selector + 1)) <= count:
        selector += 1
    return version + struct.pack(">HHHH", count, 16 << selector, selector, 16 * count - (16 << selector))


def _adjust(data, head_at):
    """Writes head's checkSumAdjustment for a font file that is this whole data."""
    struct.pack_into(">I", data, head_at + 8, 0)
    struct.pack_into(">I", data, head_at + 8, (0xB1B0AFBA - checksum(data)) & 0xFFFFFFFF)


def sfnt(tables, version=b"\x00\x01\x00\x00"):
    """An sfnt of these tables ({tag: bytes}), in tag order, with right checksums and checkSumAdjustment."""
    tags = sorted(tables)
    out = bytearray(_directory_header(version, len(tags)) + b"\0" * (16 * len(tags)))
    head_at = None
    for k, tag in enumerate(tags):
        data = tables[tag]
        if tag == b"head":
            head_at = len(out)
        struct.pack_into(">4sIII", out, 12 + 16 * k, tag, checksum(data), len(out), len(data))
        out += data + b"\0" * (-len(data) % 4)
    if head_at is not None:
        _adjust(out, head_at)
    return bytes(out)


def collection(fonts):
    """A TrueType collection of these fonts ({tag: bytes} each); a table equal in two fonts is stored once."""
    count = len(fonts)
    out = bytearray(b"ttcf" + struct.pack(">HHI", 1, 0, count) + b"\0" * (4 * count))
    bases = []
    for k, tables in enumerate(fonts):
        bases.append(len(out))
        struct.pack_into(">I", out, 12 + 4 * k, len(out))
        out += _directory_header(b"\x00\x01\x00\x00", len(tables)) + b"\0" * (16 * len(tables))
    stored = {}
    for k, tables in enumerate(fonts):
        for n, tag in enumerate(sorted(tables)):
            data = tables[tag]
            if (tag, data) not in stored:
                stored[(tag, data)] = len(out)
                out += data + b"\0" * (-len(data) % 4)
            struct.pack_into(">4sIII", out, bases[k] + 12 + 16 * n, tag, checksum(data), stored[(tag, data)], len(data))
    return bytes(out)


def woff(tables, version=b"\x00\x01\x00\x00", compress=True):
    tags = sorted(tables)
    directory, body = b"", b""
    at = 44 + 20 * len(tags)
    for tag in tags:
        data = tables[tag]
        packed = zlib.compress(data) if compress else data
        if len(packed) >= len(data):
            packed = data
        directory += struct.pack(">4sIIII", tag, at + len(body), len(packed), len(data), checksum(data))
        body += packed + b"\0" * (-len(packed) % 4)
    header = struct.pack(">4s4sIHHIHHIIIII", b"wOFF", version, 44 + len(directory) + len(body), len(tags), 0,
                         12 + 16 * len(tags) + sum(len(t) + (-len(t) % 4) for t in tables.values()), 1, 0, 0, 0, 0, 0, 0)
    return header + directory + body


WOFF2_INDEX = {b"head": 1, b"GPOS": 27, b"GSUB": 28}


def base128(value):
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.insert(0, 0x80 | (value & 0x7F))
        value >>= 7
    return b"".join(struct.pack(">B", b) for b in out)


def u255(value):
    if value < 253:
        return struct.pack(">B", value)
    return struct.pack(">BH", 253, value)


def woff2(fonts, collection_of=None):
    """A WOFF2 whose compressed stream is not compressed (the tests' "brotli" is the identity): fonts is one font's
    {tag: bytes}, or with collection_of a list of every table [(tag, bytes)] and collection_of each font's indexes."""
    entries = sorted(fonts.items()) if collection_of is None else list(fonts)
    directory, stream = b"", b""
    for tag, data in entries:
        index = WOFF2_INDEX.get(tag)
        directory += (struct.pack(">B", index) if index is not None else struct.pack(">B", 63) + tag) + base128(len(data))
        stream += data
    flavor = b"\x00\x01\x00\x00"
    if collection_of is not None:
        flavor = b"ttcf"
        directory += struct.pack(">I", 0x00010000) + u255(len(collection_of))
        for indexes in collection_of:
            directory += u255(len(indexes)) + b"\x00\x01\x00\x00" + b"".join(u255(i) for i in indexes)
    header = struct.pack(">4s4sIHHIIHHIIIII", b"wOF2", flavor, 48 + len(directory) + len(stream), len(entries), 0,
                         0, len(stream), 1, 0, 0, 0, 0, 0, 0)
    return header + directory + stream


def tables_of(data, base=0):
    """{tag: (offset, length, checksum)} of the font whose offset table is at base."""
    count = struct.unpack_from(">H", data, base + 4)[0]
    found = {}
    for k in range(count):
        tag, check, offset, length = struct.unpack_from(">4sIII", data, base + 12 + 16 * k)
        found[tag] = (offset, length, check)
    return found
