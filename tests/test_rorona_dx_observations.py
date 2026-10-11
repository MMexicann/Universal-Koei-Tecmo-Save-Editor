"""Read-only mapping leads; no native edit/load or editor claim."""
from dataclasses import replace
import math
import os
from pathlib import Path
import struct
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.research.rorona_dx import inspection, observations
from tests.test_rorona_dx_candidate import procedural_candidate


class RoronaObservationsTests(unittest.TestCase):
    def test_early_leads_offsets_width_and_opaque_byte_preservation(self):
        raw = bytearray(procedural_candidate())
        doc = inspection.inspect(bytes(raw))
        struct.pack_into('<I', raw, doc.chunks[2].payload_offset, 456789)
        for i in range(observations.CHARACTER_COUNT):
            struct.pack_into('<iii', raw, doc.chunks[3].payload_offset + i * 0x1F4,
                             i, 10 + i, 321 + i)
        base = doc.chunks[6].payload_offset
        struct.pack_into('<iiI9i', raw, base, -1, -1, 0x42480000, *range(9))
        struct.pack_into('<iiI9i', raw, base + 0x30, 109, 209, 0x42F00000,
                         *range(-9, 0))
        encoded = bytes(raw)
        document = inspection.inspect(encoded)
        found = observations.observe(document)
        self.assertEqual(found.cole, 456789)
        self.assertEqual(found.characters[0].offset + 8, 0xBB0C)
        self.assertEqual(found.characters[11].experience, 332)
        self.assertEqual(len(found.items), 2100)
        self.assertTrue(found.items[0].empty_marker)
        self.assertFalse(found.items[1].empty_marker)
        self.assertEqual(found.items[1].quality, 120)
        self.assertEqual(found.items[1].following_words, tuple(range(-9, 0)))
        self.assertEqual(inspection.unchanged(document), encoded)
        self.assertFalse(document.editable)
        self.assertFalse(document.integrity_qualified)

    def test_nonfinite_quality_and_unusual_words_are_observations_only(self):
        raw = bytearray(procedural_candidate())
        base = inspection.inspect(bytes(raw)).chunks[6].payload_offset
        struct.pack_into('<iiI', raw, base, -2, 99999, 0x7FC12345)
        doc = inspection.inspect(bytes(raw))
        item = observations.observe(doc).items[0]
        self.assertEqual(item.quality_bits, 0x7FC12345)
        self.assertTrue(math.isnan(item.quality))
        self.assertFalse(item.empty_marker)
        self.assertEqual((item.record_word, item.item_word), (-2, 99999))
        self.assertEqual(inspection.unchanged(doc), bytes(raw))

    def test_forged_or_foreign_inspection_rejected_before_observation(self):
        doc = inspection.inspect(procedural_candidate())
        for bad in (None, replace(doc, editable=True),
                    replace(doc, integrity_qualified=True),
                    replace(doc, chunks=doc.chunks[:-1]),
                    replace(doc, raw=bytearray(doc.raw))):
            with self.subTest(kind=type(bad)), self.assertRaises(SaveError):
                observations.observe(bad)

    def test_optional_genuine_copies_preserve_original_and_match_early_leads(self):
        chosen = os.environ.get('RORONA_DX_CANDIDATE_DIR')
        if not chosen:
            self.skipTest('No privately copied Rorona DX gameplay directory supplied.')
        files = tuple(Path(chosen).rglob('gamedata*'))
        self.assertTrue(files)
        self.assertLessEqual(len(files), 99)
        for path in files:
            with self.subTest(slot=path.name):
                with path.open('rb') as source:
                    raw = source.read(inspection.SAVE_SIZE + 1)
                doc = inspection.inspect(raw)
                found = observations.observe(doc)
                self.assertEqual(found.cole, struct.unpack_from('<I', raw, 0xBAF8)[0])
                self.assertEqual(tuple(c.native_id for c in found.characters),
                                 tuple(range(12)))
                for item in found.items:
                    self.assertEqual(item.quality_bits,
                                     struct.unpack_from('<I', raw, item.offset + 8)[0])
                self.assertEqual(inspection.unchanged(doc), raw)


if __name__ == '__main__':
    unittest.main()
