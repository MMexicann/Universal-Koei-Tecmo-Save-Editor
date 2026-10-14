"""Four unregistered native inspectors reject foreign framing and unsafe claims."""

from dataclasses import replace
import os
from pathlib import Path
import struct
import tempfile
import unittest

from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.research.arland_plus_vita import inspector as vita
from koei_editor.research.gundam2_ps3 import inspector as gundam
from tests.test_ps3_expansion import PS3ContextTests


def vita_fixture(profile):
    raw = bytearray(profile.size)
    raw[:4] = struct.pack("<I", profile.magic)
    offset = 32
    for tag, size in enumerate(profile.chunk_sizes, 1):
        struct.pack_into("<II", raw, offset, tag, size)
        raw[offset + 8 : offset + 8 + size] = bytes([tag]) * size
        offset += 8 + size
    struct.pack_into("<II", raw, offset, 1024, profile.trailer_size)
    return bytes(raw)


def vita_metadata(title):
    key = b"PARENT_DIRECTORY\0"
    value = ("/" + title).encode() + b"\0"
    return (
        struct.pack("<5I", 0x46535000, 0x101, 36, 36 + len(key), 1)
        + struct.pack("<HH3I", 0, 0x204, len(value), len(value), 0)
        + key
        + value
    )


def gundam_fixture():
    raw = bytearray(bytes(range(256)) * (gundam.SAVE_SIZE // 256))
    struct.pack_into(">I", raw, 0, 13)
    struct.pack_into(">2I", raw, 0x14, 32, 0x3D400)
    struct.pack_into(">I", raw, 0x10, sum(raw[0x20:]) & 0xFFFFFFFF)
    return bytes(raw)


class CandidateTests(unittest.TestCase):
    def test_vita_exact_own_title_chunks_and_uninterpreted_scalar_have_no_writer(self):
        for profile in vita.PROFILES.values():
            raw = vita_fixture(profile)
            doc = vita.decode(raw, profile.id)
            report = vita.inspect(doc)
            self.assertEqual(doc.raw, raw)
            self.assertFalse(report["registered_editor"])
            self.assertTrue(report["read_only"])
            self.assertFalse(report["native_checksum_established"])
            self.assertEqual(report["chunks"][-1]["tag"], 1024)
            self.assertEqual(len(report["chunks"]), len(profile.chunk_sizes) + 1)
            with self.assertRaises(SaveError):
                get_game(profile.id)
            for bad in (raw[:-1], raw + b"\0", bytearray(raw)):
                with self.assertRaises(SaveError):
                    vita.decode(bad, profile.id)
            other = bytearray(raw)
            other[36] ^= 1
            with self.assertRaises(SaveError):
                vita.decode(bytes(other), profile.id)
            for other_profile in vita.PROFILES.values():
                if other_profile != profile:
                    with self.assertRaises(SaveError):
                        vita.decode(raw, other_profile.id)
        for name in ("save_as", "serialize", "stage", "maximums"):
            self.assertFalse(hasattr(vita, name))

    def test_vita_snapshot_forgery_title_binding_and_changed_metadata(self):
        profile = vita.PROFILES["totori_plus_vita"]
        doc = vita.decode(vita_fixture(profile), profile.id)
        for forged in (
            replace(doc, profile=None),
            replace(doc, profile=replace(profile)),
            replace(doc, raw=bytearray(doc.raw)),
            replace(doc, chunks=list(doc.chunks)),
            replace(doc, source=None),
        ):
            with self.assertRaises(SaveError):
                vita.inspect(forged)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "USR-DATA0000"
            source.write_bytes(doc.raw)
            context = root / "sce_sys/param.sfo"
            context.parent.mkdir()
            context.write_bytes(vita_metadata(profile.title_id))
            opened = vita.read_save(source, profile.id)
            self.assertTrue(vita.inspect(opened)["original_context_bound"])
            context.write_bytes(vita_metadata("PCSE00466"))
            with self.assertRaises(SaveError):
                vita.read_save(source, profile.id)
            with self.assertRaises(SaveError):
                vita.inspect(opened)
        for context in (
            b"",
            bytearray(vita_metadata(profile.title_id)),
            vita_metadata(profile.title_id) + b"\0" * 4097,
        ):
            with self.assertRaises(SaveError):
                vita.title_context(context, profile.title_id)

    def test_gundam_native_checksum_and_foreign_revision_no_repair_or_growth_writer(
        self,
    ):
        raw = gundam_fixture()
        doc = gundam.decode(raw)
        report = gundam.inspect(doc)
        self.assertTrue(report["native_checksum_valid"])
        self.assertEqual(len(report["pilots"]), 4)
        for offset in (0, 0x10, 0x14, 0x18, 0x173, len(raw) - 1):
            bad = bytearray(raw)
            bad[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(SaveError):
                gundam.decode(bytes(bad))
        with self.assertRaises(SaveError):
            gundam.decode(bytearray(raw))
        with self.assertRaises(SaveError):
            get_game("gundam2_ps3")
        self.assertFalse(hasattr(gundam, "save_as"))
        self.assertFalse(hasattr(gundam, "serialize"))
        self.assertEqual(doc.raw, raw)

    def test_gundam_original_us_eu_context_qualified_and_japan_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "DATA.BIN"
            source.write_bytes(gundam_fixture())
            context = root / "PARAM.SFO"
            for title in gundam.TITLE_IDS:
                context.write_bytes(PS3ContextTests.metadata(title + "-00"))
                self.assertTrue(
                    gundam.inspect(gundam.read_save(source))["original_context_bound"]
                )
            for directory in ("BLJM60111-01", "BLUS30703-00", "BLUS30288-000"):
                context.write_bytes(PS3ContextTests.metadata(directory))
                with self.assertRaises(SaveError):
                    gundam.read_save(source)

    def test_optional_independent_native_candidate_directory(self):
        selected = os.environ.get("EXPANSION_CANDIDATE_COPIES")
        if not selected:
            self.skipTest("No private independent candidate references selected")
        root = Path(selected)
        for profile in vita.PROFILES.values():
            files = list(
                (root / (profile.id.replace("_", "-") + "-native")).rglob("USR-DATA*")
            )
            self.assertTrue(files)
            for path in files:
                self.assertTrue(
                    vita.inspect(vita.read_save(path, profile.id))[
                        "original_context_bound"
                    ]
                )
        for folder in (
            "gundam2-us-qualified",
            "gundam2-us-qualified-e",
            "gundam2-eu-qualified",
        ):
            self.assertTrue(
                gundam.inspect(gundam.read_save(root / folder / "DATA.BIN"))[
                    "native_checksum_valid"
                ]
            )
