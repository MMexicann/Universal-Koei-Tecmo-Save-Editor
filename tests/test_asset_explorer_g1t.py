"""Procedural-only regression tests for the bounded G1T texture subset."""

import struct
import unittest

from koei_editor.research.asset_explorer.g1t import (
    G1TFormatError,
    MAX_FILE_SIZE,
    MAX_TEXTURE_COUNT,
    TextureRecord,
    parse_g1t,
)


FORMAT_CASES = (
    (0x01, "BGRA8", 64, 0x40),
    (0x02, "RGBA8", 64, 0x40),
    (0x06, "DXT1", 8, 0x40),
    (0x59, "DXT1", 8, 0x40),
    (0x08, "DXT5", 16, 0x40),
    (0x5B, "DXT5", 16, 0x40),
)


def _mip_sizes(format_code, width, height, count):
    format_name = next(name for code, name, _, _ in FORMAT_CASES if code == format_code)
    sizes = []
    for level in range(count):
        mip_width = max(1, width >> level)
        mip_height = max(1, height >> level)
        if format_name in ("BGRA8", "RGBA8"):
            sizes.append(mip_width * mip_height * 4)
        else:
            block_bytes = 8 if format_name == "DXT1" else 16
            sizes.append(max(1, (mip_width + 3) // 4)
                         * max(1, (mip_height + 3) // 4) * block_bytes)
    return sizes


def synthetic_g1t(textures=(), version=b"0600", *, table_padding=b""):
    """Build a synthetic archive; no game bytes or asset data are used."""
    textures = tuple(textures)
    count = len(textures)
    normal_flags_offset = 0x1C
    table_offset = normal_flags_offset + count * 4 + len(table_padding)
    if table_offset % 4:
        raise ValueError("synthetic table padding must keep the table aligned")
    offset_table_end = table_offset + count * 4
    header = bytearray(offset_table_end)
    header[:4] = b"GT1G"
    header[4:8] = version
    struct.pack_into("<I", header, 0x0C, table_offset)
    struct.pack_into("<I", header, 0x10, count)
    for index, texture in enumerate(textures):
        struct.pack_into("<I", header, normal_flags_offset + index * 4,
                         texture.get("normal_flags", 0))
    header[normal_flags_offset + count * 4:table_offset] = table_padding

    body = bytearray()
    relative_offsets = []
    for texture in textures:
        width = texture.get("width", 4)
        height = texture.get("height", 4)
        format_code = texture.get("format_code", 0x01)
        mip_payloads = tuple(texture.get("mip_payloads", ()))
        if not mip_payloads:
            sizes = _mip_sizes(format_code, width, height, texture.get("mip_count", 1))
            marker = texture.get("marker", 0x40)
            mip_payloads = tuple(bytes([marker + level]) * size
                                 for level, size in enumerate(sizes))
        mip_count = len(mip_payloads)
        flags = texture.get("flags", 0)
        extra_header = texture.get("extra_header", bytes(range(12)))
        relative_offsets.append(len(header) + len(body) - table_offset)
        dimensions = width.bit_length() - 1 | ((height.bit_length() - 1) << 4)
        body.extend(struct.pack("<BBHI", mip_count << 4, format_code, dimensions, flags))
        if flags >> 24 == 0x10:
            if len(extra_header) != 12:
                raise ValueError("extra header must be twelve synthetic bytes")
            body.extend(extra_header)
        for mip_payload in mip_payloads:
            body.extend(mip_payload)

    for index, relative in enumerate(relative_offsets):
        struct.pack_into("<I", header, table_offset + index * 4, relative)
    archive = header + body
    struct.pack_into("<I", archive, 0x08, len(archive))
    return bytes(archive)


class G1TParserTests(unittest.TestCase):
    def test_supported_versions_and_format_codes_return_exact_base_payload(self):
        for version in (b"0600", b"0601", b"0602"):
            for format_code, format_name, expected_size, marker in FORMAT_CASES:
                with self.subTest(version=version, format_code=format_code):
                    raw = synthetic_g1t(({
                        "format_code": format_code,
                        "marker": marker,
                        "normal_flags": 3,
                    },), version=version)
                    record, = parse_g1t(raw)
                    self.assertEqual(record, TextureRecord(
                        index=0,
                        width=4,
                        height=4,
                        version=version.decode("ascii"),
                        format_code=format_code,
                        format_name=format_name,
                        mip_count=1,
                        payload_offset=0x1C + 4 + 4 + 8,
                        payload_size=expected_size,
                        mip_payload_sizes=(expected_size,),
                        entry_end=len(raw),
                        archive_size=len(raw),
                        normal_map_flags=3,
                        flags=0,
                    ))
                    self.assertEqual(record.read_mip(raw), bytes([marker]) * expected_size)
                    self.assertEqual(record.read_mip(memoryview(raw)), bytes([marker]) * expected_size)

    def test_mip_chain_extra_header_and_multiple_records_are_bounded(self):
        raw = synthetic_g1t((
            {"format_code": 0x02, "width": 4, "height": 4,
             "mip_count": 3, "flags": 0x10000000, "normal_flags": 3,
             "marker": 0x50},
            {"format_code": 0x59, "width": 4, "height": 4,
             "normal_flags": 1, "marker": 0x70},
        ), table_padding=b"\xA0\xA1\xA2\xA3")
        first, second = parse_g1t(raw)
        self.assertEqual((first.index, first.width, first.height, first.mip_count), (0, 4, 4, 3))
        self.assertEqual(first.mip_payload_sizes, (64, 16, 4))
        self.assertEqual(first.payload_size, 64)
        self.assertEqual(first.normal_map_flags, 3)
        self.assertEqual(first.read_mip(raw, 1), bytes([0x51]) * 16)
        self.assertEqual(first.read_mip(raw, 2), bytes([0x52]) * 4)
        self.assertEqual(second.format_name, "DXT1")
        self.assertEqual(second.read_mip(raw), bytes([0x70]) * 8)

    def test_table_order_can_differ_from_texture_data_order(self):
        raw = bytearray(synthetic_g1t((
            {"format_code": 0x01, "marker": 0x31},
            {"format_code": 0x59, "marker": 0x61},
        )))
        first_offset = struct.unpack_from("<I", raw, 0x24)[0]
        second_offset = struct.unpack_from("<I", raw, 0x28)[0]
        struct.pack_into("<I", raw, 0x24, second_offset)
        struct.pack_into("<I", raw, 0x28, first_offset)

        first, second = parse_g1t(raw)
        self.assertEqual((first.index, first.format_name), (0, "DXT1"))
        self.assertEqual((second.index, second.format_name), (1, "BGRA8"))
        self.assertEqual(first.read_mip(raw), bytes([0x61]) * 8)
        self.assertEqual(second.read_mip(raw), bytes([0x31]) * 64)

    def test_non_bytes_input_and_invalid_mip_reads_fail_cleanly(self):
        raw = synthetic_g1t(({"format_code": 0x01},))
        record, = parse_g1t(raw)
        with self.assertRaises(TypeError):
            parse_g1t("GT1G")
        with self.assertRaises(TypeError):
            record.read_mip(raw, True)
        for level in (-1, 1):
            with self.subTest(level=level), self.assertRaises(IndexError):
                record.read_mip(raw, level)
        with self.assertRaises(TypeError):
            record.read_mip(object())
        with self.assertRaises(G1TFormatError):
            record.read_mip(raw[:-1])

    def test_header_magic_version_and_declared_size_are_checked(self):
        good = synthetic_g1t(({"format_code": 0x01},))
        for raw in (b"", good[:0x1B]):
            with self.subTest(size=len(raw)), self.assertRaises(G1TFormatError):
                parse_g1t(raw)
        for offset, value in ((0, b"NOPE"), (4, b"0603")):
            damaged = bytearray(good)
            damaged[offset:offset + 4] = value
            with self.subTest(offset=offset), self.assertRaises(G1TFormatError):
                parse_g1t(damaged)
        for declared in (len(good) - 1, len(good) + 1, MAX_FILE_SIZE + 1):
            damaged = bytearray(good)
            struct.pack_into("<I", damaged, 0x08, declared)
            with self.subTest(declared=declared), self.assertRaises(G1TFormatError):
                parse_g1t(damaged)

    def test_table_count_and_offsets_are_checked_before_reading_entries(self):
        good = synthetic_g1t(({"format_code": 0x01},))
        cases = []

        damaged = bytearray(good)
        struct.pack_into("<I", damaged, 0x10, MAX_TEXTURE_COUNT + 1)
        cases.append(damaged)

        damaged = bytearray(good)
        struct.pack_into("<I", damaged, 0x0C, 0x1B)
        cases.append(damaged)

        damaged = bytearray(good)
        struct.pack_into("<I", damaged, 0x0C, 0x1D)
        cases.append(damaged)

        damaged = bytearray(good)
        struct.pack_into("<I", damaged, 0x0C, len(good) - 4)
        cases.append(damaged)

        damaged = bytearray(good)
        struct.pack_into("<I", damaged, 0x20, 0)
        cases.append(damaged)

        damaged = bytearray(good)
        struct.pack_into("<I", damaged, 0x20, 0xFFFFFFF0)
        cases.append(damaged)

        for index, raw in enumerate(cases):
            # Keep the self-described size consistent except for the oversized
            # count case, whose count gate intentionally precedes table reads.
            if index:
                struct.pack_into("<I", raw, 0x08, len(raw))
            with self.subTest(case=index), self.assertRaises(G1TFormatError):
                parse_g1t(raw)

    def test_truncated_or_unsupported_texture_headers_are_rejected(self):
        good = synthetic_g1t(({"format_code": 0x01},))
        # Make the sole table entry point at the last byte, keeping the file
        # size/header valid so the record-boundary check is what rejects it.
        table_offset = 0x1C + 4
        for absolute in (len(good) - 1, len(good) - 4):
            damaged = bytearray(good)
            relative = absolute - table_offset
            struct.pack_into("<I", damaged, table_offset, relative)
            with self.subTest(absolute=absolute), self.assertRaises(G1TFormatError):
                parse_g1t(damaged)

        for mip_header, format_code, dimensions in (
            (0x10, 0xFF, 0x0032),
            (0x00, 0x01, 0x0032),
            (0x01, 0x01, 0x0032),
            (0x10, 0x01, 0x0100),
        ):
            damaged = bytearray(good)
            entry = 0x1C + 4 + 4
            struct.pack_into("<BBH", damaged, entry, mip_header, format_code, dimensions)
            with self.subTest(header=(mip_header, format_code, dimensions)), self.assertRaises(G1TFormatError):
                parse_g1t(damaged)

    def test_mip_chain_cannot_cross_next_entry_or_exceed_size_limits(self):
        raw = synthetic_g1t((
            {"format_code": 0x02, "width": 4, "height": 4,
             "mip_count": 3, "marker": 0x20},
            {"format_code": 0x01, "width": 1, "height": 1, "marker": 0x30},
        ))
        first, _second = parse_g1t(raw)
        # Point the second entry into the first entry's payload, tightening
        # the first record boundary so its three-level chain no longer fits.
        damaged = bytearray(raw)
        second_entry_relative_offset = struct.unpack_from("<I", damaged, 0x28)[0]
        first_payload_start = first.payload_offset
        new_second_relative = first_payload_start + 20 - (0x1C + 8)
        struct.pack_into("<I", damaged, 0x28, new_second_relative)
        struct.pack_into("<I", damaged, 0x08, len(damaged))
        with self.assertRaises(G1TFormatError):
            parse_g1t(damaged)

        too_large = synthetic_g1t(({
            "format_code": 0x02,
            "width": 32768,
            "height": 32768,
            "mip_payloads": (b"x",),
        },))
        with self.assertRaises(G1TFormatError):
            parse_g1t(too_large)
        self.assertGreater(second_entry_relative_offset, 0)


if __name__ == "__main__":
    unittest.main()
