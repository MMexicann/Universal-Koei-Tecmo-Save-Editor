"""Observed Switch export qualification; procedural data is not playable save proof."""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.hyrule_definitive import parser as p


def procedural_raw():
    raw = bytearray(p.SAVE_SIZE)
    raw[:4] = p.LAYOUT_MARKER
    raw[12:16] = p.SAVE_SIZE.to_bytes(4, 'little')
    raw[p.RUPEES_OFFSET:p.RUPEES_OFFSET + 4] = (12345).to_bytes(4, 'little')
    raw[0x1AFE:0x1B00] = (12).to_bytes(2, 'little')
    raw[0x1B00:0x1B02] = (1000).to_bytes(2, 'little')
    raw[0x33084] = 1
    raw[0x3308C:0x33090] = (1603734).to_bytes(4, 'little')
    raw[0x33094] = 68
    for index in range(p.WEAPON_COUNT):
        offset = p.WEAPON_BASE + index * p.WEAPON_STRIDE
        raw[offset + 0x10:offset + 0x12] = b'\xff\xff'
    offset = p.WEAPON_BASE
    raw[offset:offset + 2] = (1000).to_bytes(2, 'little')
    raw[offset + 0x10:offset + 0x12] = (212).to_bytes(2, 'little')
    raw[offset + 0x12:offset + 0x14] = (280).to_bytes(2, 'little')
    raw[offset + 0x14:offset + 0x16] = (4).to_bytes(2, 'little')
    raw[offset + 0x16:offset + 0x1E] = bytes([5] + [255] * 7)
    raw[offset + 0x1E] = 3
    raw[-16:] = bytes(range(16))
    return bytes(raw)


class DefinitiveFormatTests(unittest.TestCase):
    def test_unchanged_and_surgical_little_endian_edit(self):
        raw = procedural_raw()
        document = p.decode(raw)
        self.assertEqual(p.serialize(document, {}), raw)
        result = p.serialize(document, {'material_1afe': 999, 'rupees': 56})
        expected = bytearray(raw)
        expected[0x1AFE:0x1B00] = (999).to_bytes(2, 'little')
        expected[p.RUPEES_OFFSET:p.RUPEES_OFFSET + 4] = (56).to_bytes(4, 'little')
        self.assertEqual(result, bytes(expected))
        self.assertEqual(result[-16:], raw[-16:])

    def test_existing_named_ordinary_records_only_and_no_bulk_max(self):
        document = p.decode(procedural_raw())
        self.assertEqual(set(p.field_map(document)), {'rupees', 'material_1afe', 'material_1b00', 'weapon_1_stars', 'weapon_1_skill_1_kos'})
        self.assertEqual(p.maximums(document, {}, 'Material inventory'), {})
        self.assertEqual(p.maximums(document, {}, 'Resources'), {})
        self.assertEqual(p.maximums(document, {'material_1afe': 50}, 'Material inventory'), {'material_1afe': 50})
        for key in ('material_1b02', 'food_2620', 'character_0_level'):
            with self.assertRaises(SaveError):
                p.stage(document, {}, key, 1)
        for value in (True, -1, 0, 1000, '4'):
            with self.assertRaises(SaveError):
                p.stage(document, {}, 'material_1afe', value)

    def test_malformed_and_foreign_exports_rejected(self):
        raw = procedural_raw()
        for bad in (raw[:-1], raw + b'\0', b'\0' * len(raw), raw[:12] + b'\0' * 4 + raw[16:]):
            with self.assertRaises(SaveError):
                p.decode(bad)
        with self.assertRaises(SaveError):
            p.decode(raw, 'hyrule_warriors')

    def test_immutable_snapshot_and_original_unstage(self):
        document = p.decode(procedural_raw())
        for forged in (replace(document, raw=bytearray(document.raw)),
                       replace(document, payload=bytearray(document.payload)),
                       replace(document, payload=document.payload[:-1] + b'\xff')):
            with self.assertRaises(SaveError):
                p.fields_for(forged)
        changes = p.stage(document, {}, 'material_1afe', 99)
        self.assertEqual(p.stage(document, changes, 'material_1afe', 12), {})
        unusual = bytearray(procedural_raw())
        unusual[p.RUPEES_OFFSET:p.RUPEES_OFFSET + 4] = (20_000_000).to_bytes(4, 'little')
        doc = p.decode(unusual)
        self.assertEqual(p.maximums(doc, {}, 'Resources'), {})
        self.assertEqual(p.stage(doc, {'rupees': 1}, 'rupees', 20_000_000), {})

    def test_readonly_characters_and_food_preserved(self):
        document = p.decode(procedural_raw())
        rows = p.inspection_rows(document)
        self.assertTrue(any(row['label'] == 'Link: EXP (read only)' and row['value'] == 1603734 for row in rows))
        self.assertEqual(sum(row['group'] == 'Fairy food' for row in rows), 129)
        self.assertEqual(p.serialize(document, {'rupees': 1})[0x3307A:], document.raw[0x3307A:])

    def test_weapon_inspector_includes_yuga_unknown_and_targeted_star_writer(self):
        document = p.decode(procedural_raw())
        rows = p.weapons(document)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['name'], 'Burning Frame')
        self.assertEqual(rows[0]['skills'][0], (5, 1000))
        self.assertEqual(rows[0]['stars'], 4)
        self.assertEqual(p.WEAPON_BASE + p.WEAPON_STRIDE * p.WEAPON_COUNT, p.SAVE_SIZE)
        edited = p.serialize(document, p.stage(document, {}, 'weapon_1_stars', 5))
        self.assertEqual(edited[p.WEAPON_BASE + 0x14:p.WEAPON_BASE + 0x16], b'\x05\x00')
        unknown = bytearray(document.raw)
        unknown[p.WEAPON_BASE + 0x10:p.WEAPON_BASE + 0x12] = (65534).to_bytes(2, 'little')
        row = p.weapons(p.decode(unknown))[0]
        self.assertEqual(row['name'], 'Unknown weapon ID 65534')

    def test_copy_storage_backups_restore_and_changed_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'copy.bin'
            source.write_bytes(procedural_raw())
            document = p.read_save(source)
            destination = source.with_name('edited.bin')
            p.save_as(document, {'material_1afe': 34}, destination)
            self.assertEqual(source.read_bytes(), document.raw)
            backups = list((source.parent / 'WarriorsEditorBackups').glob('*.bin'))
            self.assertEqual(len(backups), 1)
            restored = source.with_name('restored.bin')
            p.restore(backups[0], restored)
            self.assertEqual(restored.read_bytes(), document.raw)
            with self.assertRaises(FileExistsError):
                p.save_as(document, {}, destination)
            source.write_bytes(source.read_bytes()[:-1] + b'\xff')
            with self.assertRaises(SaveError):
                p.save_as(document, {}, source.with_name('other.bin'))

    @unittest.skipUnless(os.environ.get('HYRULE_DE_COPY'), 'Private native Switch export absent')
    def test_genuine_shared_native_roundtrip_and_targeted_quantity(self):
        raw = Path(os.environ['HYRULE_DE_COPY']).read_bytes()
        document = p.decode(raw)
        self.assertEqual(p.serialize(document, {}), raw)
        field = next(field for field in p.fields_for(document) if field.id.startswith('material_'))
        value = field.value(raw)
        self.assertTrue(1 <= value <= 999)
        target = value - 1 if value > 1 else 2
        edited = p.serialize(document, {field.id: target})
        self.assertEqual(edited[:field.offset], raw[:field.offset])
        self.assertEqual(edited[field.offset + 2:], raw[field.offset + 2:])
        self.assertEqual(field.value(edited), target)
