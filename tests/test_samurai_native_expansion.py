"""Samurai existing-record expansion; generated and native evidence are separate."""
import os
from pathlib import Path
import shutil
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.samurai5_pc import codec, parser as sw5
from koei_editor.games.samurai5_pc.presentation import Presentation
from koei_editor.games.sw4dx import samurai4dx_parser as dx
from koei_editor.games.sw2 import sw2_parser as sw2
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from koei_editor.shared.experimental_limits import experimental_limits
from koei_editor.shared.steam_owner import read_owner
from tests.test_samurai5_pc import procedural, sidecar
from tests.test_samurai4dx_format import procedural_raw as dx_raw, seal
from tests.test_sw2_pc_format import procedural_raw as sw2_raw


class SW5AcquiredGemsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        sidecar(self.folder)
        self.source = self.folder / 'copy.bin'
        self.owner = read_owner(self.source)
        payload = bytearray(sw5.decode(procedural(self.owner), owner=self.owner).payload)
        payload[sw5.GEM_BASE:sw5.GEM_BASE + sw5.GEM_COUNT] = bytes(sw5.GEM_COUNT)
        for index, quantity in ((0, 7), (11, 3), (19, 20), (21, 255), (200, 6), (999, 5)):
            payload[sw5.GEM_BASE + index] = quantity
        self.raw = codec.encode_file(bytes(payload), self.owner.account_id, 12345)
        self.source.write_bytes(self.raw)
        self.adapter = BoundScalarAdapter(sw5.GAME_ID, '.bin', sw5)
        self.doc = self.adapter.read_save(self.source)

    def test_only_held_ranked_stacks_are_writable_and_choices_do_not_acquire(self):
        fields = sw5.field_map(self.doc)
        gems = {key for key in fields if key.startswith('skill_gem_')}
        self.assertEqual(gems, {'skill_gem_11', 'skill_gem_19', 'skill_gem_21', 'skill_gem_999'})
        self.assertIn('ID 1, rank 1', fields['skill_gem_11'].label)
        for key in ('skill_gem_0', 'skill_gem_12', 'skill_gem_200', 'skill_gem_1000'):
            with self.subTest(key=key), self.assertRaises(SaveError):
                self.adapter.stage(self.doc, {}, key, 1)
        table = next(table for table in Presentation(sw5, sw5.GAME_ID).inspection_tables(self.doc)
                     if table.title == 'Skill-gem quantities')
        self.assertTrue(any(row[0] == 0 and 'inspection only' in row[-1] for row in table.rows))

    def test_hard_native_stack_bounds_types_complete_map_and_unusual_original(self):
        for enabled in (False, True):
            with experimental_limits(enabled):
                for value in (0, -1, 21, 256, True, 1.0, '2'):
                    with self.subTest(enabled=enabled, value=value), self.assertRaises(SaveError):
                        sw5.stage(self.doc, {}, 'skill_gem_11', value)
        for changes in ({'skill_gem_11': 0}, {'skill_gem_12': 20}, {'skill_gem_11': True}):
            for operation in (sw5.serialize, sw5.review, sw5.maximums):
                with self.subTest(changes=changes, operation=operation.__name__), self.assertRaises(SaveError):
                    operation(self.doc, changes)
        changes = self.adapter.stage(self.doc, {}, 'skill_gem_21', 2)
        self.assertEqual(self.adapter.stage(self.doc, changes, 'skill_gem_21', 255), {})
        self.assertEqual(self.adapter.serialize(self.doc, {}), self.raw)

    def test_max_review_unstage_and_surgical_native_checkpoint_preservation(self):
        changes = sw5.maximums(self.doc, {}, 'Acquired skill gems')
        self.assertEqual(changes, {'skill_gem_11': 20, 'skill_gem_999': 20})
        lowered = sw5.stage(self.doc, {}, 'skill_gem_19', 1)
        self.assertNotIn('skill_gem_19', sw5.maximums(self.doc, lowered, 'Acquired skill gems'))
        self.assertNotIn('skill_gem_21', sw5.maximums(self.doc, {'skill_gem_21': 1}, 'Acquired skill gems'))
        self.assertEqual([field.id for field, _, _ in sw5.review(self.doc, changes)], list(changes))
        output = self.adapter.serialize(self.doc, changes)
        reopened = self.adapter.decode(output, source=self.source)
        changed = {index for index, (a, b) in enumerate(zip(self.doc.payload, reopened.payload)) if a != b}
        self.assertEqual(changed, {sw5.GEM_BASE + 11, sw5.GEM_BASE + 999})
        self.assertEqual(output[-4:], self.raw[-4:])
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_bound_save_as_backup_restore_and_noop(self):
        changes = self.adapter.stage(self.doc, {}, 'skill_gem_11', 20)
        reopened = self.adapter.save_as(self.doc, changes, self.folder / 'edited.bin')
        self.assertEqual(sw5.field_map(reopened)['skill_gem_11'].value(reopened.payload), 20)
        self.assertEqual(self.adapter.serialize(reopened, {}), reopened.raw)
        snapshot = self.adapter.backup(self.doc)
        restored = self.adapter.restore(snapshot, self.folder / 'restored.bin')
        self.assertEqual(restored.read_bytes(), self.raw)
        self.assertEqual(self.source.read_bytes(), self.raw)


class SamuraiNativeChoiceTests(unittest.TestCase):
    def test_dx_choices_match_owned_pool_and_native_flags(self):
        doc = dx.decode(dx_raw())
        choices = dx.field_options(doc, 'officer_0_equipped_weapon')
        self.assertEqual([value for value, _ in choices], [0, 1])
        self.assertTrue(all('Blaze' in label for _, label in choices))
        self.assertEqual(dx.field_options(doc, 'weapon_0_0_skill_0_active'), ((0, 'Locked'), (1, 'Active')))
        self.assertEqual([value for value, _ in dx.field_options(doc, 'officer_0_unlocked')], [1])
        for slot, _ in choices:
            reopened = dx.decode(dx.serialize(doc, dx.stage(doc, {}, 'officer_0_equipped_weapon', slot)))
            self.assertEqual(dx.field_map(reopened)['officer_0_equipped_weapon'].value(reopened.payload), slot)
        payload = bytearray(doc.payload)
        payload[dx.OFFICER_BASE + 0x3B] = 255
        unusual = dx.decode(seal(payload))
        pending = dx.stage(unusual, {}, 'officer_0_equipped_weapon', 1)
        self.assertEqual(dx.stage(unusual, pending, 'officer_0_equipped_weapon', 255), {})
        self.assertEqual(dx.serialize(unusual, {}), unusual.raw)

    def test_original_sw2_rank_choices_preserve_separate_high_flag(self):
        doc = sw2.decode(sw2_raw())
        choices = sw2.field_options(doc, 'officer_0_skill_0')
        self.assertEqual([rank for rank, _ in choices], [1, 2, 3])
        field = sw2.field_map(doc)['officer_0_skill_0']
        for rank, _ in choices:
            reopened = sw2.decode(sw2.serialize(doc, sw2.stage(doc, {}, field.id, rank)))
            self.assertEqual(reopened.payload[field.offset], 0x80 | rank)
        self.assertIn('ID 1', sw2.field_options(doc, 'officer_0_equipped_weapon')[0][1])


class SamuraiExpansionGuiTests(unittest.TestCase):
    def test_sw5_acquired_stack_apply_review_undo_and_save(self):
        from koei_editor.games.samurai5_pc.editor import Editor
        SW5AcquiredGemsTests.setUp(self)
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        root.withdraw()
        self.addCleanup(root.destroy)
        editor = Editor(root)
        errors = []
        with patch('koei_editor.shared.verified_gui.messagebox.showerror', side_effect=lambda *args: errors.append(args)):
            with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(self.source)):
                editor.open()
            editor.group.set('Acquired skill gems')
            editor.search.set('skill_gem_11')
            editor.refresh()
            self.assertEqual(editor.fields.get_children(), ('skill_gem_11',))
            editor.fields.selection_set('skill_gem_11')
            editor.value.set('20')
            editor.apply_selected()
            self.assertEqual(editor.changes, {'skill_gem_11': 20})
            editor.review()
            editor.undo()
            self.assertEqual(editor.changes, {})
            editor.stage_values({'skill_gem_11': 20})
            editor.save_to(self.folder / 'gui-edited.bin')
            self.assertEqual(sw5.field_map(sw5.read_save(self.folder / 'gui-edited.bin'))['skill_gem_11'].value(editor.document.payload), 20)
        self.assertFalse(errors)
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_dx_native_choice_selection_stages_equipment(self):
        from koei_editor.games.sw4dx.samurai4dx_editor import Editor
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        root.withdraw()
        self.addCleanup(root.destroy)
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'copy.dat'
            source.write_bytes(dx_raw())
            editor = Editor(root)
            with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                editor.open()
            editor.group.set('Equipment')
            editor.refresh()
            editor.fields.selection_set('officer_0_equipped_weapon')
            editor.selected()
            choice = next(label for label, value in editor._choice_values.items() if value == 1)
            self.assertIn('Weapon 2', choice)
            self.assertIn('Blaze', choice)
            editor.choice_value.set(choice)
            editor.selected_choice()
            editor.apply_selected()
            self.assertEqual(editor.changes, {'officer_0_equipped_weapon': 1})
            editor.undo()
            self.assertEqual(editor.changes, {})


class SamuraiNativeExpansionEvidenceTests(unittest.TestCase):
    def test_genuine_sw5_each_acquired_stack_surgical_and_combined_save(self):
        source, owner = os.environ.get('SW5_PC_SAVE_COPY'), os.environ.get('SW5_PC_OWNER_COPY')
        if not source or not owner:
            self.skipTest('Set private SW5_PC_SAVE_COPY and SW5_PC_OWNER_COPY for native gem qualification.')
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            path = folder / 'copy.bin'
            shutil.copyfile(source, path)
            shutil.copyfile(owner, folder / 'steam_autocloud.vdf')
            adapter = BoundScalarAdapter(sw5.GAME_ID, '.bin', sw5)
            doc = adapter.read_save(path)
            self.assertEqual(adapter.serialize(doc, {}), doc.raw)
            gems = [field for field in adapter.fields_for(doc) if field.group == 'Acquired skill gems']
            self.assertTrue(gems)
            changes = {}
            for field in gems:
                target = 19 if field.value(doc.payload) == 20 else 20
                individual = adapter.stage(doc, {}, field.id, target)
                reopened = adapter.decode(adapter.serialize(doc, individual), source=path)
                self.assertEqual(field.value(reopened.payload), target)
                self.assertEqual({i for i, (a, b) in enumerate(zip(doc.payload, reopened.payload)) if a != b}, {field.offset})
                changes = adapter.stage(doc, changes, field.id, target)
            reopened = adapter.save_as(doc, changes, folder / 'edited.bin')
            self.assertEqual(reopened.payload, adapter.changed_payload(doc, changes))
            self.assertEqual(path.read_bytes(), doc.raw)
            snapshot = adapter.backup(doc)
            self.assertEqual(adapter.restore(snapshot, folder / 'restored.bin').read_bytes(), doc.raw)


if __name__ == '__main__':
    unittest.main()
