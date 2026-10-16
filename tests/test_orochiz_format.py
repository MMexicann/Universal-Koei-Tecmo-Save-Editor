"""Native Orochi Z proof-backed properties; public inputs are procedural."""
from dataclasses import replace
from functools import lru_cache
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.orochiz import orochiz_codec as codec
from koei_editor.games.orochiz import orochiz_parser as backend
from tests.scalar_contract import ScalarContractTests


@lru_cache(maxsize=1)
def procedural_raw():
    raw = bytearray((index * 23 + 11) & 255 for index in range(codec.SAVE_SIZE))
    struct.pack_into('<H', raw, 4, codec.REVISION)
    struct.pack_into('<I', raw, 8, codec.MARKER)
    for officer in range(backend.OFFICER_COUNT):
        start = backend.OFFICER_BASE + officer * backend.OFFICER_STRIDE
        for weapon in range(backend.WEAPON_COUNT):
            offset = start + backend.WEAPON_BASE + weapon * backend.WEAPON_STRIDE
            raw[offset:offset + backend.WEAPON_STRIDE] = bytes(backend.WEAPON_STRIDE)
            struct.pack_into('<H', raw, offset, backend.EMPTY_WEAPON)
    first = backend._weapon_offset(0, 0)
    struct.pack_into('<HHHBB', raw, first, 2, (1 << 0) | (1 << 5) | (1 << 14), 0x4000, 3, 7)
    raw[first + 8] = 2
    raw[first + 13] = 3  # Enum 5 stays read only, including its rank byte.
    raw[first + 22] = 19  # Unusual higher existing rank must survive Max.
    last = backend._weapon_offset(95, 7)
    struct.pack_into('<HHHBB', raw, last, 380, 0, 0, 0, 0)
    struct.pack_into('<I', raw, backend.STOCK_EXP_OFFSET, 347)
    struct.pack_into('<H', raw, backend.OFFICER_BASE + 8, 88)
    struct.pack_into('<H', raw, backend.OFFICER_BASE + 95 * backend.OFFICER_STRIDE + 8, 103)
    return codec.encode(raw)


class OrochiZFormatTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.source = self.folder / 'orochiz-copy.dat'
        self.source.write_bytes(procedural_raw())
        self.document = backend.read_save(self.source)

    def test_profile_revision_marker_all_integrity_bytes_and_opaque_tail(self):
        raw = procedural_raw()
        self.assertEqual(backend.serialize(self.document, {}), raw)
        self.assertTrue(backend.FORMAT.sample_verified)
        self.assertFalse(backend.FORMAT.game_load_verified)
        for bad in (None, [], memoryview(raw), b'', raw[:-1], raw + b'\0', bytes(len(raw))):
            with self.subTest(kind=type(bad).__name__), self.assertRaises(SaveError):
                codec.decode(bad)
        for offset in (4, 8, 500, codec.CHECKSUM_OFFSET, codec.CHECKSUM_OFFSET + 4,
                       codec.CHECKSUM_OFFSET + 19):
            changed = bytearray(raw)
            changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(SaveError):
                codec.decode(changed)
        changed = bytearray(raw)
        changed[-1] ^= 1
        self.assertEqual(codec.decode(changed), bytes(changed))
        self.assertEqual(codec.encode(changed), bytes(changed))

    def test_exact_mapping_existing_only_and_rank_display_conversion(self):
        fields = backend.field_map(self.document)
        # The distinctive procedural bytes happen to contain two ordinary
        # additional base stats. The legacy weapon/attack domain stays intact.
        self.assertEqual(len([field for field in fields.values()
                              if field.group != 'Officer base stats']), 103)
        self.assertEqual(fields['officer_0_weapon_0_attribute_0_level'].value(self.document.payload), 3)
        self.assertEqual(fields['officer_0_weapon_0_attribute_14_level'].value(self.document.payload), 20)
        for key in ('officer_0_weapon_0_attribute_5_level', 'officer_0_weapon_1_attack_bonus',
                    'officer_0_weapon_0_id', 'officer_0_exp', 'officer_0_proficiency',
                    'officer_0_level', 'officer_0_weapon_0_alchemy'):
            with self.subTest(key=key), self.assertRaises(SaveError):
                backend.stage(self.document, {}, key, 1)
        pending = backend.stage(self.document, {}, 'officer_0_weapon_0_attribute_0_level', 10)
        raw = backend.serialize(self.document, pending)
        offset = fields['officer_0_weapon_0_attribute_0_level'].offset
        self.assertEqual(raw[offset], 9)
        self.assertEqual(backend.decode(raw).payload[offset], 9)
        self.assertEqual(backend.stage(self.document, pending, 'officer_0_weapon_0_attribute_0_level', 3), {})

    def test_bulk_max_only_safe_properties_preserves_high_values_and_dependencies(self):
        raw = self.document.raw
        changes = backend.maximums(self.document, {})
        self.assertNotIn('officer_0_weapon_0_attribute_14_level', changes)
        result = backend.serialize(self.document, changes)
        fields = backend.field_map(self.document)
        allowed = set(range(codec.CHECKSUM_OFFSET, codec.CHECKSUM_OFFSET + 4))
        for key in changes:
            field = fields[key]
            allowed.update(range(field.offset, field.offset + field.size))
        touched = {index for index, (before, after) in enumerate(zip(raw, result)) if before != after}
        self.assertLessEqual(touched, allowed)
        first = backend._weapon_offset(0, 0)
        self.assertEqual(result[first:first + 6], raw[first:first + 6])
        self.assertEqual(result[first + 13], raw[first + 13])
        self.assertEqual(result[first + 22], 19)
        self.assertEqual(result[-16:], raw[-16:])
        self.assertEqual(self.source.read_bytes(), raw)
        higher = bytearray(raw)
        struct.pack_into('<I', higher, backend.STOCK_EXP_OFFSET, 200000)
        higher[first + 7] = 30
        doc = backend.decode(codec.encode(higher))
        maximum = backend.maximums(doc, {})
        self.assertNotIn('stock_exp', maximum)
        self.assertNotIn('officer_0_weapon_0_attack_bonus', maximum)
        self.assertEqual(backend.serialize(doc, maximum)[backend.STOCK_EXP_OFFSET:backend.STOCK_EXP_OFFSET + 4],
                         higher[backend.STOCK_EXP_OFFSET:backend.STOCK_EXP_OFFSET + 4])

    def test_slot_capacity_cannot_drop_owned_attributes_unusual_weapon_retained(self):
        key = 'officer_0_weapon_0_attribute_slots'
        self.assertEqual(backend.field_map(self.document)[key].minimum, 3)
        for value in (2, -1, 9, True, 3.0, '4'):
            with self.subTest(value=value), self.assertRaises(SaveError):
                backend.stage(self.document, {}, key, value)
        first = backend._weapon_offset(0, 0)
        for offset, value in ((first + 6, 2), (first + 6, 9), (first + 3, 0x80)):
            raw = bytearray(self.document.raw)
            raw[offset] = value
            doc = backend.decode(codec.encode(raw))
            self.assertFalse(any(field.id.startswith('officer_0_weapon_0_')
                                 for field in backend.fields_for(doc)))
            saved = backend.serialize(doc, backend.maximums(doc, {}))
            self.assertEqual(saved[first:first + 24], raw[first:first + 24])

    def test_independent_base_attack_officer_caps_and_progression_preservation(self):
        doc = self.document
        fields = backend.field_map(doc)
        first = fields['officer_0_base_attack']
        last = fields['officer_95_base_attack']
        self.assertEqual((first.minimum, first.maximum), (88, 409))
        self.assertEqual((last.minimum, last.maximum), (103, 461))
        self.assertEqual(backend.BASE_ATTACK_MAXIMUMS[88], 400)
        for value in (87, 410, True):
            with self.subTest(value=value), self.assertRaises(SaveError):
                backend.stage(doc, {}, first.id, value)
        result = backend.serialize(doc, backend.maximums(doc, {}, 'Officer attack'))
        self.assertEqual(first.value(result), 409)
        self.assertEqual(last.value(result), 461)
        for before, after in zip(backend.officers(doc), backend.officers(backend.decode(result))):
            self.assertEqual({key: value for key, value in before.items() if key != 'stats'},
                             {key: value for key, value in after.items() if key != 'stats'})
            self.assertEqual(before['stats'][:2] + before['stats'][3:],
                             after['stats'][:2] + after['stats'][3:])
        raw = bytearray(doc.raw)
        struct.pack_into('<H', raw, first.offset, 900)
        above = backend.decode(codec.encode(raw))
        changes = backend.maximums(above, {}, 'Officer attack')
        self.assertNotIn(first.id, changes)
        self.assertEqual(first.value(backend.serialize(above, changes)), 900)
        staged = backend.stage(above, {}, first.id, 409)
        self.assertEqual(backend.stage(above, staged, first.id, 900), {})

    def test_snapshot_forging_invalid_manual_values_and_review(self):
        doc = self.document
        for forged in (replace(doc, raw=bytearray(doc.raw)), replace(doc, payload=bytearray(doc.payload)),
                       replace(doc, format=replace(doc.format, id='other')),
                       replace(doc, payload=doc.payload[:-1] + bytes([doc.payload[-1] ^ 1]))):
            with self.assertRaises(SaveError):
                backend.serialize(forged, {})
        for value in (100000, -1, True, 1.0, '4'):
            with self.subTest(value=value), self.assertRaises(SaveError):
                backend.stage(doc, {}, 'stock_exp', value)
        changes = backend.stage(doc, {}, 'stock_exp', 99999)
        self.assertEqual([(field.id, before, after) for field, before, after in backend.review(doc, changes)],
                         [('stock_exp', 347, 99999)])
        with self.assertRaises(SaveError):
            backend.maximums(doc, {'officer_0_exp': 100})

    def test_save_backup_restore_and_changed_source_copy_safety(self):
        snapshot = backend.backup(self.document)
        self.assertEqual(snapshot.read_bytes(), self.document.raw)
        destination = self.folder / 'edited.dat'
        updated = backend.save_as(self.document, {'stock_exp': 1000}, destination)
        # Windows may expand an 8.3 temporary-folder spelling when resolving it.
        self.assertTrue(updated.source.samefile(destination))
        self.assertEqual(backend.field_map(updated)['stock_exp'].value(updated.payload), 1000)
        self.assertEqual(self.source.read_bytes(), self.document.raw)
        restored = backend.restore(snapshot, self.folder / 'restored.dat')
        self.assertEqual(restored.read_bytes(), self.document.raw)
        with self.assertRaises(FileExistsError):
            backend.save_as(self.document, {}, destination)
        self.source.write_bytes(self.document.raw[:-1] + bytes([self.document.raw[-1] ^ 1]))
        with self.assertRaises(SaveError):
            backend.save_as(self.document, {}, self.folder / 'changed-source.dat')
        self.assertFalse((self.folder / 'changed-source.dat').exists())

    def test_restore_native_validation_even_rehashed_invalid_backup(self):
        backup = backend.backup(self.document)
        raw = bytearray(backup.read_bytes())
        raw[20] ^= 1
        backup.write_bytes(raw)
        manifest = backup.with_suffix('.json')
        metadata = json.loads(manifest.read_text())
        import hashlib
        metadata['sha256'] = hashlib.sha256(raw).hexdigest()
        manifest.write_text(json.dumps(metadata))
        with self.assertRaises(SaveError):
            backend.restore(backup, self.folder / 'invalid.dat')
        self.assertFalse((self.folder / 'invalid.dat').exists())

    def test_inspection_all_records_no_progression_or_identity_writes(self):
        self.assertEqual(len(backend.officers(self.document)), 96)
        self.assertEqual(len(backend.weapons(self.document)), 768)
        self.assertEqual(backend.weapons(self.document)[-1]['id'], 380)
        self.assertEqual(backend.record_label(768, 'Weapons'), 'Officer 96: Weapon 8')
        from koei_editor.games.orochiz.orochiz_editor import OrochiZPresentation
        tables = OrochiZPresentation(backend, backend.GAME_ID).inspection_tables(self.document)
        self.assertEqual([len(table.rows) for table in tables], [96, 768])
        maximum = backend.maximums(self.document, {})
        changed_doc = backend.decode(backend.serialize(self.document, maximum))
        for before, after in zip(backend.officers(self.document), backend.officers(changed_doc)):
            self.assertEqual(before['exp'], after['exp'])
            self.assertEqual(before['stored_level'], after['stored_level'])
            self.assertEqual(before['proficiency'], after['proficiency'])
            self.assertEqual(before['equipped_slot'], after['equipped_slot'])
            for index, key in enumerate(('life', 'musou', 'attack', 'defense', 'speed')):
                field_id = f"officer_{before['id']}_base_{key}"
                expected = maximum.get(field_id, before['stats'][index])
                self.assertEqual(after['stats'][index], expected)

    @unittest.skipUnless(os.environ.get('OROCHIZ_NATIVE_SAVE'), 'Private genuine native fixture not supplied')
    def test_independent_genuine_native_roundtrip_every_qualified_field(self):
        source = Path(os.environ['OROCHIZ_NATIVE_SAVE'])
        raw = source.read_bytes()
        doc = backend.decode(raw)
        self.assertEqual(backend.serialize(doc, {}), raw)
        count = 0
        for field in backend.fields_for(doc):
            original = field.value(raw)
            options = backend.field_options(doc, field.id)
            value = (next(number for number, _label in options if number != original)
                     if options else field.minimum if original != field.minimum else field.maximum)
            result = backend.serialize(doc, {field.id: value})
            self.assertEqual(field.value(backend.decode(result).payload), value)
            allowed = set(range(field.offset, field.offset + field.size)) | set(
                range(codec.CHECKSUM_OFFSET, codec.CHECKSUM_OFFSET + 4))
            self.assertLessEqual({index for index, (before, after) in enumerate(zip(raw, result))
                                 if before != after}, allowed)
            count += 1
        self.assertGreater(count, 190)
        maximum = backend.maximums(doc, {})
        max_raw = backend.serialize(doc, maximum)
        for field in backend.fields_for(doc):
            original = field.value(raw)
            if original > field.maximum:
                self.assertNotIn(field.id, maximum)
                self.assertEqual(field.value(max_raw), original)
        for before, after in zip(backend.officers(doc), backend.officers(backend.decode(max_raw))):
            self.assertEqual({key: value for key, value in before.items() if key != 'stats'},
                             {key: value for key, value in after.items() if key != 'stats'})
            for index, key in enumerate(('life', 'musou', 'attack', 'defense', 'speed')):
                field_id = f"officer_{before['id']}_base_{key}"
                expected = maximum.get(field_id, before['stats'][index])
                self.assertEqual(after['stats'][index], expected)
        for row in backend.weapons(doc):
            if row['id'] == backend.EMPTY_WEAPON:
                start = backend._weapon_offset(row['officer'], row['slot'])
                self.assertEqual(max_raw[start:start + 24], raw[start:start + 24])
        self.assertEqual(source.read_bytes(), raw)


class OrochiZScalarContract(ScalarContractTests, unittest.TestCase):
    game_id = 'orochiz'
    payload_integrity_offsets = frozenset(range(codec.CHECKSUM_OFFSET, codec.CHECKSUM_OFFSET + 4))

    def fixture_bytes(self):
        return procedural_raw()
