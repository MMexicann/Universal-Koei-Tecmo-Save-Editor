"""Partial native integrity is never treated as a writable PS3 adapter."""
from dataclasses import replace
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.research.ninja_gaiden_3_razors_edge_ps3 import inspection as p
from tests import test_ps3_expansion as context_fixtures


def fixture():
    raw = bytearray((i * 17 + 31) & 255 for i in range(p.SIZE))
    struct.pack_into('>II', raw, 0, p.SIZE, p.REVISION)
    raw[8:12] = bytes(4)
    raw[16:20] = b'\x01\0\0\0'
    raw[24:32] = bytes(8)
    struct.pack_into('>I', raw, 20, 0x1234ABCD)
    struct.pack_into('>I', raw, 12, p.metadata_crc(raw[16:28]))
    struct.pack_into('>I', raw, 0x11E8, 12345)
    struct.pack_into('>I', raw, 0x11F0, 67890)
    return bytes(raw)


class RazorEdgeInspectionTests(unittest.TestCase):
    def test_metadata_known_answer_and_noop_are_not_full_integrity(self):
        self.assertEqual(p.metadata_crc(b'123456789'), 0xFC891918)
        raw = fixture()
        snapshot = p.inspect(raw)
        self.assertTrue(snapshot.metadata_crc_verified)
        self.assertFalse(snapshot.integrity_verified)
        self.assertFalse(snapshot.writable)
        self.assertFalse(snapshot.title_verified)
        self.assertEqual((snapshot.ryu_karma, snapshot.ayane_karma), (12345, 67890))
        self.assertEqual(snapshot.unresolved_payload_checksum, 0x1234ABCD)
        self.assertEqual(p.encode(snapshot), raw)
        changed = bytearray(raw)
        changed[0x11E8] ^= 1
        with self.assertRaises(SaveError):
            p.encode(snapshot, bytes(changed))
        # Gameplay corruption cannot be detected with the metadata-only CRC.
        partial = p.inspect(bytes(changed))
        self.assertFalse(partial.integrity_verified)
        self.assertFalse(partial.writable)

    def test_foreign_geometry_and_metadata_corruption_are_rejected(self):
        raw = fixture()
        for invalid in (raw[:-1], raw + b'0', bytearray(raw), None, {}, b'0' * p.SIZE):
            with self.subTest(kind=type(invalid).__name__), self.assertRaises(SaveError):
                p.inspect(invalid)
        for offset in (0, 4, 8, 12, 16, 20, 24, 28):
            changed = bytearray(raw)
            changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(SaveError):
                p.inspect(bytes(changed))

    def test_forged_snapshot_and_repaired_metadata_do_not_enable_writes(self):
        doc = p.inspect(fixture())
        for invalid in (None, {}, replace(doc, revision=True), replace(doc, writable=True),
                        replace(doc, writable=0), replace(doc, integrity_verified=True),
                        replace(doc, metadata_crc_verified=1), replace(doc, ryu_karma=0),
                        replace(doc, title_verified=True), replace(doc, context_sha256='z' * 64)):
            with self.assertRaises(SaveError):
                p.encode(invalid)
        raw = bytearray(doc.raw)
        raw[20] ^= 1
        struct.pack_into('>I', raw, 12, p.metadata_crc(raw[16:28]))
        repaired = p.inspect(bytes(raw))
        self.assertFalse(repaired.integrity_verified)
        with self.assertRaises(SaveError):
            p.encode(doc, repaired.raw)

    def test_original_title_context_is_bounded_and_required(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'story.dat'
            source.write_bytes(fixture())
            sfo = source.parent / 'PARAM.SFO'
            for title in ('NPUB31184STORY_P_SAV0', 'NPUB31184STORY_P_SAVE-00000000'):
                sfo.write_bytes(context_fixtures.PS3ContextTests.metadata(title))
                snapshot = p.read_save(source)
                self.assertTrue(snapshot.title_verified)
                self.assertEqual(p.encode(snapshot), source.read_bytes())
            for title in ('NPUB31184SYSTEM_SAVE', 'NPUB31184STORY_P_SAVE-invalid',
                          'NPUB31449-SAVEDATA'):
                sfo.write_bytes(context_fixtures.PS3ContextTests.metadata(title))
                with self.assertRaises(SaveError):
                    p.read_save(source)
            sfo.write_bytes(bytes(4097))
            with self.assertRaises(SaveError):
                p.read_save(source)
            sfo.unlink()
            with self.assertRaises(SaveError):
                p.read_save(source)
            with patch.object(p, '_context', side_effect=['0' * 64, '1' * 64]):
                with self.assertRaises(SaveError):
                    p.read_save(source)

    def test_genuine_native_story_copies(self):
        paths = os.environ.get('NG3_RAZORS_EDGE_PS3_EXPORT_COPIES', '')
        if not paths:
            self.skipTest('Private title-labelled native story copies were not supplied.')
        for name in paths.split(os.pathsep):
            snapshot = p.read_save(Path(name))
            self.assertTrue(snapshot.metadata_crc_verified)
            self.assertTrue(snapshot.title_verified)
            self.assertFalse(snapshot.integrity_verified)
            self.assertFalse(snapshot.writable)
            self.assertEqual(p.encode(snapshot), snapshot.raw)
