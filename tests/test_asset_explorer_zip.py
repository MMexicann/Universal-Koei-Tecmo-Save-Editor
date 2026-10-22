from __future__ import annotations

import io
import mmap
from pathlib import Path
import stat
import struct
import tempfile
import time
import unittest
import warnings
import zipfile

from koei_editor.research.asset_explorer.zip_archive import (
    DEFAULT_MAX_READ_BYTES,
    MAX_CENTRAL_DIRECTORY_BYTES,
    MAX_COMPRESSION_RATIO,
    MAX_MEMBERS,
    MAX_MEMBER_UNCOMPRESSED_BYTES,
    ZipArchiveError,
    parse_zip_archive,
    read_member,
)


def make_zip(entries: list[tuple[str, bytes, zipfile.ZipInfo | None]], *, compression: int = zipfile.ZIP_STORED) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=compression) as archive:
        for name, data, info in entries:
            if info is None:
                archive.writestr(name, data)
            else:
                archive.writestr(info, data)
    return output.getvalue()


def central_records(data: bytes) -> tuple[int, list[int]]:
    eocd_at = data.rfind(b"PK\x05\x06")
    if eocd_at < 0:
        raise AssertionError("synthetic ZIP has no EOCD")
    eocd = struct.unpack_from("<4s4H2LH", data, eocd_at)
    count, size, offset = eocd[4], eocd[5], eocd[6]
    start = eocd_at - size
    if offset > start:
        raise AssertionError("unexpected central directory offset")
    positions = []
    cursor = start
    for _ in range(count):
        positions.append(cursor)
        fields = struct.unpack_from("<4s6H3I5H2I", data, cursor)
        cursor += 46 + fields[10] + fields[11] + fields[12]
    return eocd_at, positions


def patch_central(data: bytes, index: int, field_offset: int, fmt: str, value: int) -> bytes:
    result = bytearray(data)
    _, records = central_records(data)
    struct.pack_into(fmt, result, records[index] + field_offset, value)
    return bytes(result)


def add_zip64_end_record(data: bytes, *, declared_count: int) -> bytes:
    eocd_at, _ = central_records(data)
    end = bytearray(data[eocd_at:])
    fields = struct.unpack_from("<4s4H2LH", end, 0)
    central_size, central_offset = fields[5:7]
    struct.pack_into("<H", end, 8, 0xFFFF)
    struct.pack_into("<H", end, 10, 0xFFFF)
    zip64_eocd = struct.pack(
        "<4sQ2H2L4Q",
        b"PK\x06\x06",
        44,
        45,
        45,
        0,
        0,
        declared_count,
        declared_count,
        central_size,
        central_offset,
    )
    locator = struct.pack("<4sLQL", b"PK\x06\x07", 0, eocd_at, 1)
    return data[:eocd_at] + zip64_eocd + locator + bytes(end)


class ZipAssetExplorerTests(unittest.TestCase):
    def test_lists_and_reads_members_without_extracting(self) -> None:
        raw = make_zip(
            [
                ("assets/portrait.bin", b"portrait-bytes", None),
                ("assets/mesh.bin", b"mesh-bytes", None),
                ("empty/", b"", None),
            ],
            compression=zipfile.ZIP_DEFLATED,
        )
        archive = parse_zip_archive(raw)

        self.assertEqual(len(archive.entries), 3)
        portrait, mesh, directory = archive.entries
        self.assertEqual((portrait.index, portrait.name, portrait.size), (0, "assets/portrait.bin", 14))
        self.assertEqual(portrait.id, parse_zip_archive(raw).entries[0].id)
        self.assertNotEqual(portrait.id, mesh.id)
        self.assertEqual(read_member(raw, portrait), b"portrait-bytes")
        self.assertEqual(read_member(memoryview(raw), mesh), b"mesh-bytes")
        self.assertTrue(directory.is_directory)
        with self.assertRaises(ZipArchiveError):
            read_member(raw, directory)

    def test_accepts_paths_and_seekable_streams_and_preserves_stream_position(self) -> None:
        raw = make_zip([("item.dat", b"synthetic", None)])
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "fixture.zip"
            path.write_bytes(raw)
            archive = parse_zip_archive(path)
            self.assertEqual(read_member(path, archive.entries[0]), b"synthetic")

            with path.open("rb") as stream:
                stream.seek(7)
                listed = parse_zip_archive(stream)
                self.assertEqual(stream.tell(), 7)
                self.assertEqual(read_member(stream, listed.entries[0]), b"synthetic")
                self.assertEqual(stream.tell(), 7)

    def test_accepts_read_only_mmap_without_copying_the_whole_source(self) -> None:
        raw = make_zip([("m.bin", b"mapped", None)])
        with tempfile.TemporaryFile() as stream:
            stream.write(raw)
            stream.flush()
            with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
                archive = parse_zip_archive(mapped)
                self.assertEqual(read_member(mapped, archive.entries[0]), b"mapped")

    def test_rejects_missing_or_truncated_central_directory(self) -> None:
        raw = make_zip([("x", b"x", None)])
        for damaged in (b"", raw[:10], raw[:-8]):
            with self.subTest(length=len(damaged)), self.assertRaises(ZipArchiveError):
                parse_zip_archive(damaged)

    def test_rejects_excessive_member_count_before_zipfile_listing(self) -> None:
        raw = add_zip64_end_record(
            make_zip([("x", b"x", None)]), declared_count=MAX_MEMBERS + 1
        )
        with self.assertRaisesRegex(ZipArchiveError, "member count"):
            parse_zip_archive(raw)

    def test_accepts_well_formed_zip64_directory(self) -> None:
        raw = add_zip64_end_record(make_zip([("x", b"zip64", None)]), declared_count=1)
        archive = parse_zip_archive(raw)
        self.assertEqual(read_member(raw, archive.entries[0]), b"zip64")

    def test_rejects_excessive_central_directory_size_before_listing(self) -> None:
        raw = bytearray(make_zip([("x", b"x", None)]))
        eocd_at, _ = central_records(raw)
        struct.pack_into("<L", raw, eocd_at + 12, MAX_CENTRAL_DIRECTORY_BYTES + 1)
        with self.assertRaisesRegex(ZipArchiveError, "central directory"):
            parse_zip_archive(bytes(raw))

    def test_rejects_encrypted_members(self) -> None:
        raw = bytearray(make_zip([("secret.bin", b"secret", None)]))
        _, records = central_records(raw)
        struct.pack_into("<H", raw, records[0] + 8, 0x0001)
        with self.assertRaisesRegex(ZipArchiveError, "encrypted"):
            parse_zip_archive(bytes(raw))

    def test_rejects_unsupported_compression(self) -> None:
        raw = patch_central(make_zip([("x", b"x", None)]), 0, 10, "<H", 99)
        with self.assertRaisesRegex(ZipArchiveError, "unsupported compression"):
            parse_zip_archive(raw)

    def test_rejects_path_traversal_absolute_and_windows_paths(self) -> None:
        for name in ("../outside", "a/../outside", "/absolute", "C:/drive", "a\\..\\b", "a//b", "./dot"):
            raw = make_zip([(name, b"x", None)])
            with self.subTest(name=name), self.assertRaises(ZipArchiveError):
                parse_zip_archive(raw)

    def test_rejects_duplicate_casefolded_and_file_directory_conflicts(self) -> None:
        cases = (
            [("same.txt", b"a", None), ("same.txt", b"b", None)],
            [("Same.txt", b"a", None), ("same.txt", b"b", None)],
            [("node", b"a", None), ("node/child", b"b", None)],
            [("folder/", b"", None), ("folder/", b"", None)],
        )
        for entries in cases:
            with self.subTest(entries=[entry[0] for entry in entries]):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    raw = make_zip(entries)
                with self.assertRaisesRegex(ZipArchiveError, "duplicate|conflict"):
                    parse_zip_archive(raw)

    def test_rejects_symlink_and_special_members(self) -> None:
        link = zipfile.ZipInfo("link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        raw = make_zip([("link", b"target", link)])
        with self.assertRaisesRegex(ZipArchiveError, "symbolic links"):
            parse_zip_archive(raw)

        fifo = zipfile.ZipInfo("pipe")
        fifo.create_system = 3
        fifo.external_attr = (stat.S_IFIFO | 0o600) << 16
        raw = make_zip([("pipe", b"", fifo)])
        with self.assertRaisesRegex(ZipArchiveError, "special files"):
            parse_zip_archive(raw)

    def test_rejects_file_ancestors_in_both_directory_orders(self) -> None:
        for parent, child in (
            ("node", "node/nested/leaf.bin"),
            ("NODE", "node/nested/leaf.bin"),
            ("caf\u00e9", "cafe\u0301/nested/leaf.bin"),
        ):
            entries = [(parent, b"parent", None), (child, b"child", None)]
            for ordered in (entries, list(reversed(entries))):
                with self.subTest(names=[entry[0] for entry in ordered]):
                    with self.assertRaisesRegex(ZipArchiveError, "path conflict"):
                        parse_zip_archive(make_zip(ordered))

    def test_accepts_directory_ancestors_and_sibling_prefixes(self) -> None:
        entries = [
            ("folder/deep/leaf.bin", b"leaf", None),
            ("folder", b"", zipfile.ZipInfo("folder/")),
            ("folder-two", b"sibling", None),
            ("folderish/item.bin", b"other", None),
        ]
        for ordered in (entries, list(reversed(entries))):
            with self.subTest(names=[entry[0] for entry in ordered]):
                archive = parse_zip_archive(make_zip(ordered))
                self.assertEqual(len(archive.entries), 4)
                self.assertEqual(sorted(entry.size for entry in archive.entries), [0, 4, 5, 7])

    def test_large_flat_directory_has_bounded_indexing_cost(self) -> None:
        # A flat, valid directory must not trigger an all-pairs descendant scan.
        # The generous bound allows slower CI hosts; the former scan required
        # 900 million prefix comparisons for this modest supported archive.
        count = 30_000
        raw = make_zip([(f"member-{index:05d}.bin", b"", None) for index in range(count)])
        started = time.monotonic()
        archive = parse_zip_archive(raw)
        elapsed = time.monotonic() - started
        self.assertEqual(len(archive.entries), count)
        self.assertEqual(archive.entries[-1].name, "member-29999.bin")
        self.assertLess(elapsed, 15.0, "ZIP indexing must remain bounded for many independent names")

    def test_rejects_size_and_ratio_bombs(self) -> None:
        raw = patch_central(
            make_zip([("x", b"x", None)]), 0, 24, "<L", MAX_MEMBER_UNCOMPRESSED_BYTES + 1
        )
        with self.assertRaisesRegex(ZipArchiveError, "uncompressed-size"):
            parse_zip_archive(raw)

        bomb = make_zip([("repeat.bin", b"A" * (MAX_COMPRESSION_RATIO * 1024), None)], compression=zipfile.ZIP_DEFLATED)
        with self.assertRaisesRegex(ZipArchiveError, "compression-ratio"):
            parse_zip_archive(bomb)

        total_bomb = bytearray(
            make_zip([(f"member-{index}", b"x", None) for index in range(5)])
        )
        _, records = central_records(total_bomb)
        for record in records:
            struct.pack_into("<L", total_bomb, record + 20, 2 * 1024 * 1024)
            struct.pack_into("<L", total_bomb, record + 24, MAX_MEMBER_UNCOMPRESSED_BYTES - 1)
        with self.assertRaisesRegex(ZipArchiveError, "total uncompressed size"):
            parse_zip_archive(bytes(total_bomb))

    def test_rejects_read_limit_and_stale_entry(self) -> None:
        raw = make_zip([("payload", b"payload", None)])
        entry = parse_zip_archive(raw).entries[0]
        with self.assertRaisesRegex(ZipArchiveError, "read limit"):
            read_member(raw, entry, max_bytes=2)
        with self.assertRaisesRegex(ZipArchiveError, "non-negative"):
            read_member(raw, entry, max_bytes=-1)
        self.assertEqual(DEFAULT_MAX_READ_BYTES, 64 * 1024 * 1024)

        changed = make_zip([("other", b"payload", None)])
        with self.assertRaisesRegex(ZipArchiveError, "does not match"):
            read_member(changed, entry)

    def test_crc_failure_is_rejected(self) -> None:
        raw = bytearray(make_zip([("payload", b"payload", None)]))
        _, records = central_records(raw)
        local_offset = struct.unpack_from("<L", raw, records[0] + 42)[0]
        name_size, extra_size = struct.unpack_from("<HH", raw, local_offset + 26)
        data_offset = local_offset + 30 + name_size + extra_size
        raw[data_offset] ^= 0x01
        corrupted = bytes(raw)
        entry = parse_zip_archive(corrupted).entries[0]
        with self.assertRaisesRegex(ZipArchiveError, "CRC"):
            read_member(corrupted, entry)

        empty = patch_central(make_zip([("empty", b"", None)]), 0, 16, "<L", 1)
        empty_entry = parse_zip_archive(empty).entries[0]
        with self.assertRaisesRegex(ZipArchiveError, "CRC"):
            read_member(empty, empty_entry)


if __name__ == "__main__":
    unittest.main()
