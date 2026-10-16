"""Independent native Orochi Z dependency and copy-safety review."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.orochiz import orochiz_codec as codec
from koei_editor.games.orochiz import orochiz_parser as parser
from tests.test_orochiz_format import procedural_raw


class OrochiZIndependentReviewTests(unittest.TestCase):
    def test_decode_freezes_mutable_input_and_subclass_snapshot_rejects(self):
        class OtherDocument(parser.Document):
            pass
        mutable = bytearray(procedural_raw())
        document = parser.decode(mutable)
        mutable[-1] ^= 1
        self.assertEqual(document.raw, procedural_raw())
        for bad in (OtherDocument(document.format, document.source, document.raw, document.payload),
                    replace(document, payload=bytearray(document.payload)),
                    replace(document, raw=bytearray(document.raw))):
            with self.assertRaises(SaveError):
                parser.maximums(bad, {})

    def test_invalid_pending_values_and_unsupported_edits_reject_before_max(self):
        document = parser.decode(procedural_raw())
        for changes in ({'stock_exp': -1}, {'stock_exp': True}, {'stock_exp': 100000},
                        {'officer_0_weapon_0_attack_bonus': 21},
                        {'officer_0_weapon_0_attribute_slots': 2},
                        {'officer_0_weapon_0_attribute_0_level': 0},
                        {'officer_0_weapon_0_attribute_0_level': 11},
                        {'officer_0_weapon_0_attribute_5_level': 10},
                        {'officer_0_weapon_0_attribute_1_level': 10},
                        {'officer_0_weapon_1_attack_bonus': 20}, {'story_complete': 1}):
            for operation in (lambda: parser.maximums(document, changes),
                              lambda: parser.limit_values(document, changes, ['stock_exp']),
                              lambda: parser.review(document, changes)):
                with self.subTest(changes=changes), self.assertRaises(SaveError):
                    operation()

    def test_capacity_counts_all_owned_bits_including_excluded_enum_and_zero_capacity(self):
        raw = bytearray(procedural_raw())
        first = parser._weapon_offset(0, 0)
        mask = sum(1 << index for index in range(8))
        struct.pack_into('<H', raw, first + 2, mask)
        raw[first + 6] = 8
        document = parser.decode(codec.encode(raw))
        field = parser.field_map(document)['officer_0_weapon_0_attribute_slots']
        self.assertEqual(field.minimum, 8)
        with self.assertRaises(SaveError):
            parser.stage(document, {}, field.id, 7)
        self.assertNotIn('officer_0_weapon_0_attribute_5_level', parser.field_map(document))
        last = parser._weapon_offset(95, 7)
        final = parser.field_map(document)['officer_95_weapon_7_attribute_slots']
        self.assertEqual(final.value(document.payload), 0)
        self.assertEqual(final.minimum, 0)
        changed = parser.serialize(document, {final.id: 8})
        self.assertEqual(changed[last:last + 6], document.raw[last:last + 6])
        self.assertEqual(changed[last + 6], 8)
        self.assertEqual(changed[last + 7:last + 24], document.raw[last + 7:last + 24])

    def test_unusual_masks_capacity_unknown_ids_and_hidden_ranks_preserved(self):
        first = parser._weapon_offset(0, 0)
        for identity, mask, capacity in ((414, 0, 0), (415, 0, 0), (65535, 0, 0),
                                         (2, 0x8000, 8), (2, 0x7FFF, 8), (2, 0, 9)):
            raw = bytearray(procedural_raw())
            struct.pack_into('<HH', raw, first, identity, mask)
            raw[first + 6] = capacity
            raw[first + 8:first + 23] = bytes(range(240, 255))
            sealed = codec.encode(raw)
            document = parser.decode(sealed)
            self.assertFalse(any(field.id.startswith('officer_0_weapon_0_')
                                 for field in parser.fields_for(document)))
            result = parser.serialize(document, parser.maximums(document, {}))
            self.assertEqual(result[first:first + 24], sealed[first:first + 24])

    def test_rank_storage_minus_one_unusual_originals_and_opaque_tail_preserved(self):
        raw = bytearray(procedural_raw())
        first = parser._weapon_offset(0, 0)
        struct.pack_into('<I', raw, parser.STOCK_EXP_OFFSET, 0xFFFFFFFF)
        raw[first + 7] = 255
        raw[first + 22] = 255
        raw[-16:] = bytes(range(16))
        sealed = codec.encode(raw)
        document = parser.decode(sealed)
        field_id = 'officer_0_weapon_0_attribute_0_level'
        for value, stored in ((1, 0), (10, 9)):
            output = parser.serialize(document, {field_id: value})
            self.assertEqual(output[first + 8], stored)
            self.assertEqual(parser.field_map(parser.decode(output))[field_id].value(output), value)
        pending = parser.maximums(document, {})
        self.assertNotIn('stock_exp', pending)
        self.assertNotIn('officer_0_weapon_0_attack_bonus', pending)
        self.assertNotIn('officer_0_weapon_0_attribute_14_level', pending)
        output = parser.serialize(document, pending)
        self.assertEqual(output[-16:], sealed[-16:])
        self.assertEqual(output[first + 13], sealed[first + 13])
        for key in ('stock_exp', 'officer_0_weapon_0_attack_bonus',
                    'officer_0_weapon_0_attribute_14_level'):
            field = parser.field_map(document)[key]
            self.assertEqual(field.value(output), field.value(sealed))
            low = parser.stage(document, {}, key, field.minimum)
            self.assertEqual(parser.stage(document, low, key, field.value(sealed)), {})

    def test_base_attack_per_officer_floor_caps_preserve_progression_and_other_stats(self):
        from koei_editor.games.orochiz.orochiz_limits import BASE_ATTACK_MINIMUMS, BASE_ATTACK_MAXIMUMS
        self.assertEqual(len(BASE_ATTACK_MINIMUMS), 96)
        self.assertEqual(len(BASE_ATTACK_MAXIMUMS), 96)
        raw = bytearray(procedural_raw())
        for officer in range(96):
            struct.pack_into('<H', raw, parser.OFFICER_BASE + officer * parser.OFFICER_STRIDE + 8,
                             BASE_ATTACK_MINIMUMS[officer])
        # Preserve anomalous existing low and high values when applying Max.
        struct.pack_into('<H', raw, parser.OFFICER_BASE + 8, 0)
        struct.pack_into('<H', raw, parser.OFFICER_BASE + parser.OFFICER_STRIDE + 8, 65535)
        document = parser.decode(codec.encode(raw))
        changes = parser.maximums(document, {}, 'Officer attack')
        self.assertEqual(len(changes), 94)
        self.assertNotIn('officer_0_base_attack', changes)
        self.assertNotIn('officer_1_base_attack', changes)
        output = parser.serialize(document, changes)
        for officer, (before, after) in enumerate(zip(parser.officers(document),
                                                       parser.officers(parser.decode(output)))):
            for key in ('stored_level', 'equipped_slot', 'proficiency', 'exp'):
                self.assertEqual(after[key], before[key])
            for index in (0, 1, 3, 4):
                self.assertEqual(after['stats'][index], before['stats'][index])
            self.assertEqual(after['stats'][2], before['stats'][2] if officer < 2
                             else BASE_ATTACK_MAXIMUMS[officer])
            field = parser.field_map(document)[f'officer_{officer}_base_attack']
            self.assertEqual(field.minimum, BASE_ATTACK_MINIMUMS[officer])
            self.assertEqual(field.maximum, BASE_ATTACK_MAXIMUMS[officer])
            for value in (field.minimum - 1, field.maximum + 1):
                # Restoring the exact unusual opened original is always allowed.
                if value == field.value(document.payload):
                    continue
                with self.assertRaises(SaveError):
                    parser.stage(document, {}, field.id, value)

    def test_source_transplant_destination_suffix_restore_same_bytes_and_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'save.dat'
            raw = procedural_raw()
            source.write_bytes(raw)
            document = parser.read_save(source)
            foreign = folder / 'foreign.dat'
            modified = bytearray(raw)
            modified[-1] ^= 1
            foreign.write_bytes(modified)
            with self.assertRaises(SaveError):
                parser.save_as(replace(document, source=foreign), {}, folder / 'transplanted.dat')
            with self.assertRaises(SaveError):
                parser.save_as(document, {}, folder / 'edited.bin')
            snapshot = parser.backup(document)
            parser.save_as(document, {'stock_exp': 1000}, folder / 'edited.dat')
            self.assertEqual(source.read_bytes(), raw)
            self.assertEqual(parser.restore(snapshot, folder / 'restored.dat').read_bytes(), raw)
            broken = bytearray(snapshot.read_bytes())
            broken[500] ^= 1
            snapshot.write_bytes(broken)
            manifest_path = snapshot.with_suffix('.json')
            manifest = json.loads(manifest_path.read_text())
            manifest['sha256'] = hashlib.sha256(broken).hexdigest()
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaises(SaveError):
                parser.restore(snapshot, folder / 'invalid.dat')
            self.assertFalse((folder / 'invalid.dat').exists())
            self.assertFalse((folder / 'transplanted.dat').exists())

    @unittest.skipUnless(os.environ.get('OROCHIZ_NATIVE_SAVE'), 'No private genuine native Orochi Z fixture')
    def test_genuine_every_field_surgical_preserves_officers_and_weapon_identity(self):
        path = Path(os.environ['OROCHIZ_NATIVE_SAVE'])
        raw = path.read_bytes()
        document = parser.decode(raw)
        count = 0
        for field in parser.fields_for(document):
            original = field.value(raw)
            options = parser.field_options(document, field.id)
            value = (next(number for number, _label in options if number != original)
                     if options else field.minimum if original != field.minimum else field.maximum)
            output = parser.serialize(document, {field.id: value})
            allowed = set(range(field.offset, field.offset + field.size)) | set(
                range(codec.CHECKSUM_OFFSET, codec.CHECKSUM_OFFSET + 4))
            self.assertLessEqual({index for index, (a, b) in enumerate(zip(raw, output)) if a != b}, allowed)
            before_officers = parser.officers(document)
            after_officers = parser.officers(parser.decode(output))
            for before, after in zip(before_officers, after_officers):
                for key in ('id', 'stored_level', 'equipped_slot', 'proficiency', 'exp'):
                    if key == 'equipped_slot' and field.id == f"officer_{before['id']}_equipped_weapon":
                        self.assertEqual(after[key], value - 1)
                    elif key == 'exp' and field.id == f"officer_{before['id']}_exp_within_level":
                        self.assertEqual(after[key], value)
                    else:
                        self.assertEqual(after[key], before[key])
                for index, stat in enumerate(('life', 'musou', 'attack', 'defense', 'speed')):
                    expected = (value if field.id == f"officer_{before['id']}_base_{stat}"
                                else before['stats'][index])
                    self.assertEqual(after['stats'][index], expected)
            self.assertEqual(output[-16:], raw[-16:])
            self.assertEqual(field.value(output), value)
            count += 1
        self.assertGreaterEqual(count, 433)
        self.assertEqual(path.read_bytes(), raw)

    @unittest.skipUnless(os.environ.get('OROCHIZ_NATIVE_SAVE'), 'No private genuine native Orochi Z fixture')
    def test_genuine_tk_copy_search_apply_review_undo_max_inspection_and_save(self):
        import tkinter as tk
        from unittest.mock import patch
        from koei_editor.games.orochiz.orochiz_editor import Editor
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.addCleanup(root.destroy)
        root.withdraw()
        original = Path(os.environ['OROCHIZ_NATIVE_SAVE'])
        raw = original.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'copy.dat'
            source.write_bytes(raw)
            editor = Editor(root)
            with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                editor.open()
            editor.group.set('Officer attack')
            editor.search.set('Base attack')
            editor.refresh()
            self.assertEqual(len(editor.fields.get_children()), 96)
            key = 'officer_0_base_attack'
            field = parser.field_map(editor.document)[key]
            value = field.minimum if field.value(raw) != field.minimum else field.maximum
            editor.fields.selection_set(key)
            editor.value.set(str(value))
            editor.apply_selected()
            self.assertEqual(editor.changes, {key: value})
            editor.review()
            editor.undo()
            self.assertEqual(editor.changes, {})
            editor.max_visible()
            for field in parser.fields_for(editor.document):
                if field.value(raw) > field.maximum or field.value(raw) < field.minimum:
                    self.assertNotIn(field.id, editor.changes)
            editor.show_inspector()
            self.assertEqual([len(table.rows) for table in editor.presentation.inspection_tables(editor.document)],
                             [96, 768])
            destination = Path(directory) / 'edited.dat'
            expected = parser.serialize(editor.document, editor.changes)
            editor.save_to(destination)
            updated = parser.read_save(destination)
            self.assertEqual(updated.raw, expected)
            self.assertEqual(source.read_bytes(), raw)
            self.assertTrue(editor.backup.exists())
            self.assertEqual(editor.backup.read_bytes(), raw)
        self.assertEqual(original.read_bytes(), raw)
