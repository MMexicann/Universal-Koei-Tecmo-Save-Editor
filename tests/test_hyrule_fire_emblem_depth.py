"""Independent mechanic constraints; procedural examples are not playable saves."""
import os
from pathlib import Path
import struct
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.hyrule_legends import parser as legends
from koei_editor.games.hyrule_legends.editor import Editor as LegendsEditor
from koei_editor.games.three_houses import parser as houses
from koei_editor.games.three_houses.editor import Editor as HousesEditor
from tests.test_hyrule_legends import procedural_legends
from tests.test_three_houses import procedural_slot, sealed


def instruction_slot(revision=23):
    raw = bytearray(procedural_slot(revision))
    base = 12 + 0x644
    struct.pack_into('<h', raw, base + 0x24, 2)
    raw[base + 0xC4] = 50
    raw[base + 0x61:base + 0x7F] = bytes(30)
    raw[base + 0x61] = 1 << 2
    raw[base + 0x62] = 1 << 1
    raw[base + 0x7F:base + 0x84] = bytes((2, 9, 240, 240, 240))
    return sealed(raw)


def trust_slot():
    raw = bytearray(procedural_legends())
    raw[legends.FAIRY_BASE + 0x1B] = 24
    raw[legends.FAIRY_BASE + 0x24] = 50
    return bytes(raw)


class ThreeHousesDepthTests(unittest.TestCase):
    motivation = 'character:0:motivation'
    ability0 = 'character:0:ability:0'
    ability2 = 'character:0:ability:2'

    def test_motivation_choice_steps_preserve_instruction_rewards_and_native_integrity(self):
        for revision in (13, 23):
            raw = instruction_slot(revision)
            document = houses.decode(raw)
            self.assertEqual(houses.serialize(document, {}), raw)
            self.assertEqual(houses.maximums(document, {}), {})
            self.assertEqual(tuple(v for v, _ in houses.field_options(document, self.motivation)),
                             (0, 25, 50, 75, 100))
            for target in (0, 25, 50, 75, 100):
                pending = houses.stage(document, {}, self.motivation, target)
                output = houses.serialize(document, pending)
                self.assertEqual(output, sealed(output))
                touched = {i for i, (a, b) in enumerate(zip(raw, output)) if a != b}
                self.assertLessEqual(touched, {0, 1, 2, 3, 12 + 0x644 + 0xC4})
                self.assertEqual(houses.stage(document, pending, self.motivation, 50), {})
            for value in (-1, 1, 26, 99, 101, True, '100', 100.0):
                with self.subTest(revision=revision, value=value), self.assertRaises(SaveError):
                    houses.stage(document, {}, self.motivation, value)

    def test_motivation_excludes_byleth_dead_unjoined_duplicate_and_unusual_records(self):
        base = 12 + 0x644
        raw = instruction_slot()
        for offset, value in ((base + 0x24, struct.pack('<h', 0)),
                              (base + 0x24, struct.pack('<h', 1)),
                              (base + 0x24, struct.pack('<h', 35)),
                              (base + 0x4A, b'\0'),
                              (base + 0xAC, struct.pack('<I', 1)),
                              (base + 0xAC, struct.pack('<I', 11)),
                              (base + 0x24C + 0x24, struct.pack('<h', 2)),
                              (base + 0xC4, b'\xff'), (base + 0xC4, b'\x33')):
            changed = bytearray(raw)
            changed[offset:offset + len(value)] = value
            changed = sealed(changed)
            document = houses.decode(changed)
            self.assertNotIn(self.motivation, houses.field_map(document))
            self.assertEqual(houses.serialize(document, {}), changed)
            self.assertEqual(houses.maximums(document, {}), {})

    def test_loadout_only_reuses_original_equipped_owned_abilities_and_rejects_duplicates(self):
        raw = instruction_slot()
        document = houses.decode(raw)
        options = houses.field_options(document, self.ability0)
        self.assertEqual(tuple(v for v, _ in options), (2, 9, 240))
        pending = houses.stage(document, {}, self.ability0, 240)
        self.assertEqual(houses.stage(document, pending, self.ability0, 2), {})
        moved = houses.stage(document, pending, self.ability2, 2)
        output = houses.serialize(document, moved)
        self.assertEqual(output[12 + 0x644 + 0x7F:12 + 0x644 + 0x84], bytes((240, 9, 2, 240, 240)))
        self.assertEqual(output, sealed(output))
        self.assertLessEqual({i for i, (a, b) in enumerate(zip(raw, output)) if a != b},
                             {0, 1, 2, 3, 12 + 0x644 + 0x7F, 12 + 0x644 + 0x81})
        self.assertEqual(houses.maximums(document, moved), moved)
        for action in (lambda: houses.stage(document, {}, self.ability2, 2),
                       lambda: houses.stage(document, moved, self.ability0, 2),
                       lambda: houses.serialize(document, {self.ability2: 2}),
                       lambda: houses.stage(document, {'unknown': 1}, self.ability0, 240),
                       lambda: houses.stage(document, {}, self.ability0, 10)):
            with self.assertRaises(SaveError):
                action()
        self.assertEqual(pending, {self.ability0: 240})
        self.assertEqual(document.raw, raw)

    def test_loadout_admission_requires_original_learned_unique_undeployed_state(self):
        raw = instruction_slot()
        base = 12 + 0x644
        for offset, value in ((base + 0x61, b'\0'), (base + 0x80, b'\x02'),
                              (base + 0x7F, b'\xff'),
                              (base + 0xAC, struct.pack('<I', 3 | (1 << 18))),
                              (base + 0x7F, bytes((240,) * 5))):
            changed = bytearray(raw)
            changed[offset:offset + len(value)] = value
            changed = sealed(changed)
            document = houses.decode(changed)
            self.assertNotIn(self.ability0, houses.field_map(document))
            self.assertEqual(houses.serialize(document, {}), changed)
            with self.assertRaises(SaveError):
                houses.serialize(document, {self.ability0: 240})

    def test_invalid_batches_reject_before_review_max_and_unstage(self):
        document = houses.decode(instruction_slot())
        for pending in ({self.motivation: 99}, {self.ability2: 2},
                        {self.ability0: True}, {'unowned': 240}):
            for action in (lambda: houses.review(document, pending),
                           lambda: houses.maximums(document, pending),
                           lambda: houses.stage(document, pending, self.motivation, 50)):
                with self.assertRaises(SaveError):
                    action()
        corrupted = bytearray(document.raw)
        corrupted[12 + 0x644 + 0xC4] ^= 1
        with self.assertRaises(SaveError):
            houses.decode(corrupted)

    @unittest.skipUnless(os.environ.get('THREE_HOUSES_REVIEW_COPIES'), 'Private reviewed native copies absent')
    def test_all_native_new_fields_are_surgical_both_revisions_and_originals_unchanged(self):
        exercised = set()
        for filename in os.environ['THREE_HOUSES_REVIEW_COPIES'].split(os.pathsep):
            source = Path(filename)
            raw = source.read_bytes()
            document = houses.decode(raw)
            self.assertEqual(houses.serialize(document, {}), raw)
            for field in houses.fields_for(document):
                if field.group not in ('Motivation', 'Existing ability loadout'):
                    continue
                target = (0 if field.value(raw) else 25) if field.group == 'Motivation' else 240
                pending = houses.stage(document, {}, field.id, target)
                output = houses.serialize(document, pending)
                self.assertEqual(output, sealed(output))
                self.assertLessEqual({i for i, (a, b) in enumerate(zip(raw, output)) if a != b},
                                     set(range(4)) | set(range(field.offset, field.offset + field.size)))
                self.assertEqual(field.value(houses.decode(output).payload), target)
                exercised.add((document.profile.revision, field.group))
            self.assertEqual(source.read_bytes(), raw)
        self.assertEqual(exercised, {(13, 'Motivation'), (23, 'Motivation'),
                                    (13, 'Existing ability loadout'), (23, 'Existing ability loadout')})


class LegendsTrustTests(unittest.TestCase):
    def test_owned_trust_decrease_preserves_level_refresh_skills_and_all_neighbors(self):
        raw = trust_slot()
        document = legends.decode(raw)
        key = 'fairy_1_trust'
        field = legends.field_map(document)[key]
        self.assertFalse(field.maxable)
        pending = legends.stage(document, {}, key, 1)
        output = legends.serialize(document, pending)
        self.assertEqual(output[:field.offset], raw[:field.offset])
        self.assertEqual(output[field.offset + 1:], raw[field.offset + 1:])
        self.assertEqual(legends.stage(document, pending, key, 50), {})
        self.assertNotIn(key, legends.maximums(document, {}))
        for value in (0, 51, 101, True, '20', 25.0):
            with self.assertRaises(SaveError):
                legends.stage(document, {}, key, value)

    def test_owned_fairy_trust_qualification_and_unusual_original_preservation(self):
        raw = trust_slot()
        for relative, value in ((0, 0), (0, 2), (0x1B, 0), (0x1B, 100),
                                (0x24, 0)):
            changed = bytearray(raw)
            changed[legends.FAIRY_BASE + relative] = value
            document = legends.decode(changed)
            self.assertNotIn('fairy_1_trust', legends.field_map(document))
            self.assertEqual(legends.serialize(document, {}), bytes(changed))
            with self.assertRaises(SaveError):
                legends.serialize(document, {'fairy_1_trust': 1})

        for value in (101, 255):
            changed = bytearray(raw)
            changed[legends.FAIRY_BASE + 0x24] = value
            document = legends.decode(changed)
            self.assertIn('fairy_1_trust', legends.field_map(document))
            self.assertEqual(legends.stage(document, {}, 'fairy_1_trust', value), {})
            self.assertEqual(legends.serialize(document, {}), bytes(changed))

    @unittest.skipUnless(os.environ.get('HYRULE_LEGENDS_COPY'), 'Private native Legends copy absent')
    def test_native_trust_controls_roundtrip_and_one_byte_edits(self):
        source = Path(os.environ['HYRULE_LEGENDS_COPY'])
        raw = source.read_bytes()
        document = legends.decode(raw)
        self.assertEqual(legends.serialize(document, {}), raw)
        fields = [f for f in legends.fields_for(document) if f.group == 'Fairy trust']
        self.assertTrue(fields)
        for field in fields:
            output = legends.serialize(document, {field.id: 1})
            self.assertLessEqual({i for i, (a, b) in enumerate(zip(raw, output)) if a != b}, {field.offset})
            self.assertEqual(field.value(legends.decode(output).payload), 1)
        self.assertEqual(source.read_bytes(), raw)


class DepthGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.errors = []
        mocked = patch('koei_editor.shared.verified_gui.messagebox.showerror',
                       side_effect=lambda *args: self.errors.append(args))
        mocked.start()
        self.addCleanup(mocked.stop)

    def run_workflow(self, backend, editor_type, raw, group, key, target):
        source = Path(self.folder.name) / ('input' + backend.EXTENSION)
        source.write_bytes(raw)
        editor = editor_type(self.root)
        with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
            editor.open()
        editor.group.set(group)
        editor.refresh()
        self.assertIn(key, editor.fields.get_children())
        editor.fields.selection_set(key)
        editor.selected()
        editor.value.set(str(target))
        editor.apply_selected()
        self.assertEqual(editor.changes, {key: target})
        editor.review()
        editor.undo()
        self.assertEqual(editor.changes, {})
        editor.fields.selection_set(key)
        editor.value.set(str(target))
        editor.apply_selected()
        editor.max_visible()
        self.assertEqual(editor.changes, {key: target})
        editor.apply_theme('Dark')
        destination = source.with_name('edited' + backend.EXTENSION)
        editor.save_to(destination)
        self.assertFalse(self.errors)
        self.assertEqual(source.read_bytes(), raw)
        reopened = backend.read_save(destination)
        self.assertEqual(backend.field_map(reopened)[key].value(reopened.payload), target)
        self.assertEqual(backend.restore(editor.backup, source.with_name('restored' + backend.EXTENSION)).read_bytes(), raw)
        return editor

    def test_motivation_named_choices_apply_review_undo_save_backup_restore(self):
        editor = self.run_workflow(houses, HousesEditor, instruction_slot(), 'Motivation',
                                   'character:0:motivation', 100)
        self.assertEqual(tuple(editor._choice_values.values()), (0, 25, 50, 75, 100))

    def test_existing_loadout_choices_apply_review_undo_and_copy_workflow(self):
        editor = self.run_workflow(houses, HousesEditor, instruction_slot(), 'Existing ability loadout',
                                   'character:0:ability:0', 240)
        self.assertIn(240, editor._choice_values.values())
        self.assertIn('Clear its old slot', houses.field_hint(editor.document, 'character:0:ability:0'))

    def test_fairy_trust_visible_no_max_apply_review_undo_and_copy_workflow(self):
        self.run_workflow(legends, LegendsEditor, trust_slot(), 'Fairy trust', 'fairy_1_trust', 25)

    @unittest.skipUnless(os.environ.get('THREE_HOUSES_REVIEW_COPIES'), 'Private reviewed native copies absent')
    def test_native_motivation_named_choice_copy_workflow(self):
        for filename in os.environ['THREE_HOUSES_REVIEW_COPIES'].split(os.pathsep):
            source = Path(filename)
            raw = source.read_bytes()
            document = houses.decode(raw)
            fields = [f for f in houses.fields_for(document) if f.group == 'Motivation']
            if fields:
                field = fields[0]
                self.run_workflow(houses, HousesEditor, raw, field.group, field.id,
                                  100 if field.value(raw) != 100 else 0)
                self.assertEqual(source.read_bytes(), raw)
                return
        self.fail('The supplied native review set must expose a qualified motivation control.')

    @unittest.skipUnless(os.environ.get('THREE_HOUSES_REVIEW_COPIES'), 'Private reviewed native copies absent')
    def test_native_existing_ability_loadout_copy_workflow(self):
        for filename in os.environ['THREE_HOUSES_REVIEW_COPIES'].split(os.pathsep):
            source = Path(filename)
            raw = source.read_bytes()
            document = houses.decode(raw)
            fields = [f for f in houses.fields_for(document)
                      if f.group == 'Existing ability loadout' and f.value(raw) != 240
                      and len(f.choices) >= 3]
            if fields:
                field = fields[0]
                self.run_workflow(houses, HousesEditor, raw, field.group, field.id, 240)
                self.assertEqual(source.read_bytes(), raw)
                return
        self.fail('The supplied native review set must expose a reusable original ability loadout.')

    @unittest.skipUnless(os.environ.get('HYRULE_LEGENDS_COPY'), 'Private native Legends copy absent')
    def test_native_owned_fairy_trust_copy_workflow(self):
        source = Path(os.environ['HYRULE_LEGENDS_COPY'])
        raw = source.read_bytes()
        document = legends.decode(raw)
        field = next(f for f in legends.fields_for(document) if f.group == 'Fairy trust')
        self.run_workflow(legends, LegendsEditor, raw, field.group, field.id, 1)
        self.assertEqual(source.read_bytes(), raw)
