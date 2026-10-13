"""Native source-backed tests; no generated SRAM is called a player save."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.nobunaga_ambition_nes import parser
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import BoundScalarAdapter


def procedural_raw():
    raw = bytearray((i * 13 + 77) % 256 for i in range(parser.SIZE))
    raw[0x1FED:0x1FF2] = b'KOEI\0'
    raw[0xD9D:0xDA1] = (17).to_bytes(2, 'little') + (1565).to_bytes(2, 'little')
    raw[0xD5F] = 2
    for index in range(17):
        raw[parser.OWNER_START + index] = index
        raw[parser.POLICY_START + index] = 255 if index == 5 else index % 6
        name = 'Tokugawa' if index == 7 else 'Oda' if index == 16 else f'Lord{index}'
        base = parser.NAME_START + index * 9
        raw[base:base + 9] = name.encode().ljust(9, b'\0')
        for relative in (0, 6):
            base = parser.PROVINCE_START + index * parser.PROVINCE_STRIDE + relative
            raw[base:base + 2] = (54321 + index).to_bytes(2, 'little')
    raw[parser.CHECKSUM_OFFSET:parser.CHECKSUM_OFFSET + 2] = parser.checksum(raw).to_bytes(2, 'little')
    return bytes(raw)


class NobunagaAmbitionNesTests(unittest.TestCase):
    def setUp(self):
        self.adapter = BoundScalarAdapter(parser.GAME_ID, '.sav', parser)
        self.raw = procedural_raw()
        self.document = self.adapter.decode(self.raw)

    def test_qualification_noop_existing_gates(self):
        self.assertTrue(self.document.format.published_format)
        self.assertFalse(self.document.format.sample_verified)
        self.assertFalse(self.document.format.game_load_verified)
        self.assertEqual(self.adapter.serialize(self.document, {}), self.raw)
        self.assertEqual(len(self.adapter.fields_for(self.document)), 32)
        self.assertNotIn('fief_5_gold', parser.field_map(self.document))
        self.assertEqual(len(parser.province_records(self.document)), 17)

    def test_native_checksum_coverage_and_exclusions(self):
        raw = bytearray(self.raw)
        initial = parser.checksum(raw)
        for offset in (0, 0x1000, parser.CHECKSUM_OFFSET, 0x1FFC):
            changed = bytearray(self.raw); changed[offset] ^= 1
            self.assertEqual(parser.checksum(changed), initial)
        for offset in (0, 0x1000, 0x1FFC):
            raw[offset] ^= 1
        for offset in (1, 0xFFF, 0x1001, 0x1FEA):
            changed = bytearray(self.raw); changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(SaveError):
                self.adapter.decode(changed)
        # Excluded bank gaps and opaque trailer are retained byte-exactly.
        self.assertEqual(parser.serialize(parser.decode(raw), {}), raw)

    def test_source_native_owner_51_state_is_preserved_and_read_only(self):
        raw = bytearray(self.raw)
        raw[parser.OWNER_START] = 51
        raw[0x1FEB:0x1FED] = parser.checksum(raw).to_bytes(2, 'little')
        document = self.adapter.decode(raw)
        self.assertEqual(self.adapter.serialize(document, {}), raw)
        self.assertNotIn('fief_0_gold', parser.field_map(document))
        self.assertNotIn('fief_0_rice', parser.field_map(document))
        self.assertIn('read only', parser.province_records(document)[0][2])

    def test_every_edit_surgical_with_native_integrity_readback(self):
        for field in self.adapter.fields_for(self.document):
            changes = self.adapter.stage(self.document, {}, field.id, 0)
            output = self.adapter.serialize(self.document, changes)
            touched = {i for i, (a, b) in enumerate(zip(self.raw, output)) if a != b}
            allowed = set(range(field.offset, field.offset + 2)) | {parser.CHECKSUM_OFFSET, parser.CHECKSUM_OFFSET + 1}
            self.assertLessEqual(touched, allowed)
            self.assertEqual(parser.checksum(output), int.from_bytes(output[0x1FEB:0x1FED], 'little'))
            reopened = self.adapter.decode(output)
            self.assertEqual(field.value(reopened.payload), 0)
            self.assertEqual(self.adapter.stage(self.document, changes, field.id, field.value(self.raw)), {})
            self.assertEqual(self.adapter.maximums(self.document, changes), changes)
            self.assertEqual(self.adapter.limit_values(self.document, changes, [field.id]), {})
            self.assertEqual(len(self.adapter.review(self.document, changes)), 1)
        self.assertEqual(self.document.raw, self.raw)

    def test_bad_types_pending_snapshot_platform_and_framing_rejected(self):
        key = 'fief_0_gold'
        for value in (-1, 54322, True, '54321', 54321.0, None):
            with self.subTest(value=value), self.assertRaises(SaveError):
                self.adapter.stage(self.document, {}, key, value)
        for changes in ({'unknown': 1}, {key: False}, [], None):
            with self.assertRaises(SaveError):
                self.adapter.serialize(self.document, changes)
        for document in (replace(self.document, source=None),
                         replace(self.document, raw=bytearray(self.raw)),
                         replace(self.document, payload=b'x' * parser.SIZE),
                         replace(self.document, format=replace(parser.FORMAT))):
            with self.assertRaises(SaveError):
                self.adapter.serialize(document, {})
        for raw in (self.raw[:-1], self.raw + b'x', b'\0' * parser.SIZE, memoryview(self.raw)):
            with self.assertRaises(SaveError):
                self.adapter.decode(raw)
        for offset, value in ((0xD9D, 50), (0xD5F, 4), (parser.OWNER_START, 17),
                              (parser.POLICY_START, 6), (parser.NAME_START + 16 * 9, 88)):
            raw = bytearray(self.raw); raw[offset] = value
            raw[0x1FEB:0x1FED] = parser.checksum(raw).to_bytes(2, 'little')
            with self.subTest(offset=offset), self.assertRaises(SaveError):
                self.adapter.decode(raw)
        with self.assertRaises(SaveError):
            parser.decode(self.raw, 'nobunaga_ambition_dos')

    def test_safe_copy_backup_restore_source_race_and_on_disk_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'copy.sav'; source.write_bytes(self.raw)
            document = self.adapter.read_save(source)
            field = self.adapter.fields_for(document)[0]
            target = root / 'edited.sav'
            saved = self.adapter.save_as(document, {field.id: 12}, target)
            self.assertEqual(saved.raw, target.read_bytes())
            self.assertEqual(source.read_bytes(), self.raw)
            backup = self.adapter.backup(document)
            restored = root / 'restored.sav'; self.adapter.restore(backup, restored)
            self.assertEqual(restored.read_bytes(), self.raw)
            with self.assertRaises(FileExistsError):
                self.adapter.save_as(document, {}, target)
            original_backup = parser.backup
            def changed_source(doc):
                result = original_backup(doc); source.write_bytes(b'x' * parser.SIZE); return result
            with patch.object(parser, 'backup', side_effect=changed_source), self.assertRaises(SaveError):
                self.adapter.save_as(document, {}, root / 'race.sav')
            self.assertFalse((root / 'race.sav').exists())


if __name__ == '__main__':
    unittest.main()
