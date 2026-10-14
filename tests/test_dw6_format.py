"""Procedural DW6 PC safety checks, plus opt-in genuine-file qualification.

Procedural records are generated independently; they are not game-load evidence.
"""
from dataclasses import replace
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw6 import dw6_parser as backend
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from tests.scalar_contract import ScalarContractTests


@lru_cache(maxsize=1)
def procedural_raw():
    raw = bytearray((index * 13 + 19) & 255 for index in range(backend.SAVE_SIZE))
    for index in range(41):
        base = 2904 + index * 168
        for slot in range(8):
            struct.pack_into('<4I', raw, base + 8 + 16 * slot,
                             index * 3 if slot == 0 else 174, 7, 3, 0)
        struct.pack_into('<8I', raw, base + 136, index, 0, 0, 0, 0, 0, 17,
                         1 if index == 0 else 0)
    for index in range(8):
        base = 10784 + index * 60
        raw[base:base + 60] = bytes(60)
        if index < 2:
            struct.pack_into('<9I', raw, base, 0, 60 + index, 3, 0,
                             341 if index == 0 else 700, 160, 201, 355, 141)
    return bytes(raw)


class DW6FormatTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.source = self.folder / 'copy.dat'
        self.source.write_bytes(procedural_raw())
        self.document = backend.read_save(self.source)

    def test_profile_identity_offsets_and_noop(self):
        self.assertEqual(backend.serialize(self.document, {}), procedural_raw())
        self.assertEqual(backend.decode(memoryview(procedural_raw())).raw, procedural_raw())
        self.assertEqual(backend.field_map(self.document)['officer_19_unlocked'].offset, 0x1874)
        self.assertEqual(backend.record_label(20), 'Xu Huang')
        self.assertFalse(backend.FORMAT.game_load_verified)
        adapter = BoundScalarAdapter('dw6', '.dat', backend)
        self.assertEqual(adapter.decode(procedural_raw()).format.id, 'dw6')
        with self.assertRaises(SaveError):
            adapter.decode(procedural_raw(), 'dw6emp')
        for raw in (None, 'save', b'', procedural_raw()[:-1], procedural_raw() + b'\0',
                    bytes(backend.SAVE_SIZE)):
            with self.subTest(kind=type(raw).__name__), self.assertRaises(SaveError):
                backend.decode(raw)
        damaged = bytearray(procedural_raw())
        struct.pack_into('<I', damaged, 2904 + 20 * 168 + 136, 19)
        with self.assertRaises(SaveError):
            backend.decode(damaged)
        # The first dimension of a shaped view is not its actual byte count.
        view = memoryview(procedural_raw() * 2).cast('B', shape=(backend.SAVE_SIZE, 2))
        with self.assertRaises(SaveError):
            backend.decode(view)

    def test_unlocks_separate_from_resource_max_and_surgical(self):
        before = self.document.raw
        changes = backend.maximums(self.document, {})
        self.assertFalse(any(key.startswith('officer') for key in changes))
        self.assertEqual(backend.unlock_values(self.document),
                         {f'officer_{index}_unlocked': 1 for index in range(1, 41)})
        self.assertEqual(backend.maximums(self.document, {}, 'Unlocks'), {})
        changes = backend.stage(self.document, {}, 'officer_19_unlocked', 1)
        self.assertEqual(backend.stage(self.document, changes, 'officer_19_unlocked', 0), {})
        updated = backend.serialize(self.document, changes)
        self.assertEqual(updated[:0x1874], before[:0x1874])
        self.assertEqual(updated[0x1878:], before[0x1878:])
        self.assertEqual(backend.field_map(backend.decode(updated))['officer_19_unlocked'].value(updated), 1)
        with self.assertRaises(SaveError):
            backend.stage(self.document, {}, 'officer_0_unlocked', 0)
        self.assertEqual([(field.id, old, new) for field, old, new in backend.review(self.document, changes)],
                         [('officer_19_unlocked', 0, 1)])

    def test_existing_horse_stats_preserve_high_values_and_neighbors(self):
        mapping = backend.field_map(self.document)
        self.assertEqual(len([f for f in mapping.values() if f.group in ('Unlocks', 'Horses', 'Weapon elements', 'Weapon bonuses')]), 41 + 8 + 41 + 41)
        self.assertIn('officer_40_weapon_0_skill_9', mapping)
        self.assertEqual(backend.maximums(self.document, {})['horse_0_speed'], 500)
        self.assertNotIn('horse_1_speed', backend.maximums(self.document, {}))
        changes = backend.stage(self.document, {}, 'horse_1_speed', 499)
        self.assertEqual(backend.stage(self.document, changes, 'horse_1_speed', 700), {})
        changes = backend.stage(self.document, {}, 'horse_0_attack', 400)
        updated = backend.serialize(self.document, changes)
        offset = 10784 + 24
        self.assertEqual(updated[:offset], self.document.raw[:offset])
        self.assertEqual(updated[offset + 4:], self.document.raw[offset + 4:])
        self.assertEqual(int.from_bytes(updated[offset:offset + 4], 'little'), 400)
        for key in ('horse_2_speed', 'horse_0_exp', 'horse_0_skills', 'weapon_0_damage',
                    'officer_0_level', 'story_complete'):
            with self.subTest(key=key), self.assertRaises(SaveError):
                backend.stage(self.document, {}, key, 1)
        with self.assertRaises(TypeError):
            mapping['fake'] = mapping['horse_0_speed']

    def test_playable_flag_is_one_byte_and_opaque_neighbors_are_preserved(self):
        raw = bytearray(self.document.raw)
        offset = backend.OFFICER_BASE + 19 * backend.OFFICER_STRIDE + 164
        raw[offset:offset + 4] = b'\x00\x61\x82\xa3'
        doc = backend.decode(bytes(raw))
        field = backend.field_map(doc)['officer_19_unlocked']
        self.assertEqual(field.size, 1)
        updated = backend.serialize(doc, backend.stage(doc, {}, field.id, 1))
        self.assertEqual(updated[:offset], doc.raw[:offset])
        self.assertEqual(updated[offset + 1:], doc.raw[offset + 1:])
        self.assertEqual(updated[offset], 1)

    def test_unusual_records_remain_read_only_and_unknown_bytes_preserved(self):
        for offset, value in ((2904 + 164, 2), (10784 + 4, 63), (10784 + 20, 0),
                              (10784 + 24, 0)):
            raw = bytearray(procedural_raw())
            struct.pack_into('<I', raw, offset, value)
            document = backend.decode(raw)
            keys = backend.field_map(document)
            if offset == 2904 + 164:
                self.assertNotIn('officer_0_unlocked', keys)
            else:
                self.assertFalse(any(key.startswith('horse_0_') for key in keys))
            result = backend.serialize(document, backend.maximums(document, {}))
            self.assertEqual(result[offset:offset + 4], bytes(raw[offset:offset + 4]))
            self.assertEqual(result[11264:], bytes(raw[11264:]))

    def test_invalid_values_changes_and_forged_snapshots_rejected(self):
        for value in (-1, 501, True, 1.0, '400'):
            with self.subTest(value=value), self.assertRaises(SaveError):
                backend.stage(self.document, {}, 'horse_0_speed', value)
        for action in (backend.serialize, backend.maximums):
            with self.assertRaises(SaveError):
                action(self.document, {'horse_2_speed': 500})
        forged = (replace(self.document, raw=bytearray(self.document.raw)),
                  replace(self.document, payload=bytearray(self.document.payload)),
                  replace(self.document, format=replace(backend.FORMAT, id='dw6emp')),
                  replace(self.document, payload=self.document.payload[:-1] + b'\0'))
        for document in forged:
            with self.subTest(document_type=type(document.raw)), self.assertRaises(SaveError):
                backend.serialize(document, {})

    def test_backups_restore_and_changed_source(self):
        snapshot = backend.backup(self.document)
        self.assertEqual(snapshot.read_bytes(), self.document.raw)
        output = self.folder / 'edited.dat'
        result = backend.save_as(self.document, {'horse_0_speed': 500}, output)
        self.assertEqual(self.source.read_bytes(), self.document.raw)
        self.assertEqual(backend.field_map(result)['horse_0_speed'].value(result.payload), 500)
        with self.assertRaises(FileExistsError):
            backend.save_as(self.document, {}, output)
        restore = self.folder / 'restored.dat'
        self.assertEqual(backend.restore(snapshot, restore).read_bytes(), self.document.raw)
        # An honest SHA in backup metadata does not qualify malformed save bytes.
        damaged = bytes(backend.SAVE_SIZE)
        snapshot.write_bytes(damaged)
        metadata_path = snapshot.with_suffix('.json')
        metadata = json.loads(metadata_path.read_text())
        metadata['sha256'] = hashlib.sha256(damaged).hexdigest()
        metadata_path.write_text(json.dumps(metadata))
        rejected = self.folder / 'foreign.dat'
        with self.assertRaises(SaveError):
            backend.restore(snapshot, rejected)
        self.assertFalse(rejected.exists())
        self.source.write_bytes(self.document.raw[:-1] + b'\0')
        with self.assertRaises(SaveError):
            backend.save_as(self.document, {}, self.folder / 'changed.dat')
        self.assertFalse((self.folder / 'changed.dat').exists())

    def test_native_live_folder_and_resolved_alias_are_rejected(self):
        live = self.folder / 'Documents' / 'KOEI' / 'DYNASTY WARRIORS 6' / 'Savedata'
        live.mkdir(parents=True)
        native = live / 'save.dat'
        native.write_bytes(self.document.raw)
        with self.assertRaises(SaveError):
            backend.read_save(native)
        with self.assertRaises(SaveError):
            backend.save_as(self.document, {}, live / 'new.dat')
        alias = self.folder / 'ordinary-folder'
        try:
            alias.symlink_to(live, target_is_directory=True)
        except OSError:
            return  # Windows may require developer mode for a directory symlink.
        with self.assertRaises(SaveError):
            backend.read_save(alias / 'save.dat')
        self.assertEqual(native.read_bytes(), self.document.raw)

    def test_named_inspection_keeps_progression_equipment_and_story_read_only(self):
        rows = backend.inspection_rows(self.document)
        self.assertEqual(len([row for row in rows if row['group'] == 'Officers']), 41)
        self.assertEqual(len([row for row in rows if row['group'] == 'Weapons']), 41)
        self.assertEqual(len([row for row in rows if row['group'] == 'Horses']), 8)
        self.assertTrue(any('Xiahou Dun / slot 1:' in row['label'] and 'ID 0;' in row['value']
                            for row in rows if row['group'] == 'Weapons'))
        output = backend.serialize(self.document, backend.maximums(self.document, {}))
        for index in range(41):
            base = 2904 + index * 168
            self.assertEqual(output[base:base + 164], self.document.raw[base:base + 164])
        self.assertEqual(output[11264:], self.document.raw[11264:])

    @unittest.skipUnless(os.environ.get('DW6_SAVE'), 'Set DW6_SAVE to a private native PC save copy.')
    def test_private_genuine_native_roundtrip_and_surgical_edits(self):
        raw = Path(os.environ['DW6_SAVE']).read_bytes()
        document = backend.decode(raw)
        self.assertEqual(backend.serialize(document, {}), raw)
        weapon_count = sum(struct.unpack_from('<I', raw, 2904 + index * 168 + 8 + slot * 16)[0] != 174
                           for index in range(41) for slot in range(8))
        self.assertGreater(weapon_count, 41)
        self.assertEqual(len(backend.inspection_rows(document)), 41 + weapon_count + 8)
        changes = backend.maximums(document, {}, 'Horses')
        edited = backend.serialize(document, changes)
        allowed = {offset for field in backend.fields_for(document) if field.id in changes
                   for offset in range(field.offset, field.offset + field.size)}
        touched = {offset for offset, pair in enumerate(zip(raw, edited)) if pair[0] != pair[1]}
        self.assertTrue(touched)
        self.assertLessEqual(touched, allowed)
        self.assertEqual(backend.decode(edited).raw, edited)
        # This qualifies parsing and preservation, never actual game-load behavior.


class DW6ScalarContractTests(ScalarContractTests, unittest.TestCase):
    game_id = 'dw6'

    def fixture_bytes(self):
        return procedural_raw()
