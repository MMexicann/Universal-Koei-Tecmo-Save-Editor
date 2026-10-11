"""Procedural bounds tests and optional independently sourced genuine-layout checks."""
from dataclasses import replace
import os
from pathlib import Path
import struct
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.research.meruru_dx import inspection as candidate
from tests.test_rorona_dx_candidate import procedural_candidate as rorona_candidate


def procedural_candidate():
    """Opaque patterned bytes with qualified framing, not a playable game save."""
    raw = bytearray((i * 31 + 11) % 256 for i in range(candidate.SAVE_SIZE))
    struct.pack_into('<I', raw, 0, candidate.MAGIC)
    offset = candidate.HEADER_SIZE
    for tag, size in enumerate(candidate.CHUNK_SIZES, 1):
        struct.pack_into('<II', raw, offset, tag, size)
        offset += 8 + size
    struct.pack_into('<II', raw, offset, candidate.TRAILER_TAG, candidate.TRAILER_SIZE)
    return bytes(raw)


class MeruruCandidateTests(unittest.TestCase):
    def test_complete_layout_opaque_preservation_and_no_gameplay_claim(self):
        raw = procedural_candidate()
        doc = candidate.inspect(raw)
        self.assertEqual(candidate.unchanged(doc), raw)
        self.assertEqual(tuple(chunk.tag for chunk in doc.chunks), tuple(range(1, 25)))
        self.assertEqual(doc.trailer_offset + doc.trailer_size, len(raw))
        self.assertEqual(doc.chunks[2].payload_offset, 0xCF9C)
        self.assertEqual(doc.chunks[10].payload_offset, 0x5493E)
        self.assertFalse(doc.editable)
        self.assertFalse(doc.qualified_game_profile)
        self.assertFalse(doc.integrity_qualified)
        self.assertNotEqual(raw[4:32], bytes(28))
        self.assertNotEqual(raw[doc.trailer_offset + 8:], bytes(doc.trailer_size - 8))

    def test_foreign_system_wrong_size_revision_and_mutable_input_rejected(self):
        raw = procedural_candidate()
        for bad in (raw[:-1], raw + b'\0', raw[:36864], rorona_candidate(),
                    bytes(len(raw)), bytearray(raw), memoryview(raw)):
            with self.subTest(kind=type(bad), size=len(bad)), self.assertRaises(SaveError):
                candidate.inspect(bad)
        bad = bytearray(raw)
        struct.pack_into('<I', bad, 0, candidate.MAGIC + 1)
        with self.assertRaises(SaveError):
            candidate.inspect(bytes(bad))

    def test_each_tag_length_and_trailer_bounds_rejected(self):
        raw = procedural_candidate()
        doc = candidate.inspect(raw)
        for chunk in doc.chunks:
            for delta, value in ((0, chunk.tag + 1), (4, chunk.size + 1), (4, 0xFFFFFFFF)):
                bad = bytearray(raw)
                struct.pack_into('<I', bad, chunk.header_offset + delta, value)
                with self.subTest(tag=chunk.tag, delta=delta, value=value), self.assertRaises(SaveError):
                    candidate.inspect(bytes(bad))
        for delta, value in ((0, 0), (4, candidate.TRAILER_SIZE - 8), (4, candidate.TRAILER_SIZE + 8)):
            bad = bytearray(raw)
            struct.pack_into('<I', bad, doc.trailer_offset + delta, value)
            with self.assertRaises(SaveError):
                candidate.inspect(bytes(bad))

    def test_forged_inspection_does_not_pass_roundtrip(self):
        raw = procedural_candidate()
        doc = candidate.inspect(raw)
        for bad in (None, replace(doc, raw=bytearray(raw)), replace(doc, editable=True),
                    replace(doc, qualified_game_profile=True), replace(doc, integrity_qualified=True),
                    replace(doc, chunks=doc.chunks[:-1]), replace(doc, trailer_size=doc.trailer_size - 8)):
            with self.subTest(kind=type(bad)), self.assertRaises(SaveError):
                candidate.unchanged(bad)

    def test_currency_observation_is_bounded_and_does_not_promote_writes(self):
        raw = procedural_candidate()
        initial = candidate.inspect(raw)
        offset = initial.chunks[2].payload_offset
        for value in (0, 1000, 364433, 9999999, 0xFFFFFFFF):
            altered = bytearray(raw)
            struct.pack_into('<I', altered, offset, value)
            observed = candidate.inspect(bytes(altered))
            lead = candidate.cole_lead(observed)
            self.assertEqual(lead.value, value)
            self.assertEqual(lead.offset, offset)
            self.assertFalse(lead.editable)
            self.assertFalse(lead.maxable)
            self.assertFalse(observed.integrity_qualified)
            self.assertEqual(candidate.unchanged(observed), bytes(altered))
        for forged in (None, replace(initial, chunks=initial.chunks[:-1]),
                       replace(initial, integrity_qualified=True),
                       replace(initial, raw=bytearray(raw))):
            with self.assertRaises(SaveError):
                candidate.cole_lead(forged)

    def test_optional_genuine_copied_layout(self):
        selected = os.environ.get('MERURU_DX_CANDIDATE_DIR')
        if not selected:
            self.skipTest('No privately copied Meruru DX candidate directory supplied.')
        files = tuple(p for p in Path(selected).rglob('*')
                      if p.is_file() and p.name.lower().startswith('gamedata'))
        self.assertTrue(files, 'No gameplay slot copies found in selected directory.')
        self.assertLessEqual(len(files), 99)
        for path in files:
            with self.subTest(slot=path.name):
                with path.open('rb') as source:
                    raw = source.read(candidate.SAVE_SIZE + 1)
                doc = candidate.inspect(raw)
                self.assertEqual(candidate.unchanged(doc), raw)
                self.assertFalse(doc.integrity_qualified)
                lead = candidate.cole_lead(doc)
                self.assertEqual(lead.value, int.from_bytes(raw[lead.offset:lead.offset + 4], 'little'))
                self.assertFalse(lead.editable)


if __name__ == '__main__':
    unittest.main()
