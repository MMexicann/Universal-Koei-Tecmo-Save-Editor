"""Copied-save navigation and dependency failures retain native pending state."""
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from tests.test_verified_editors import synthetic_raw


class ScalarWorkspaceNavigationTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def open_editor(self, game_id='dw8xl', raw=None):
        game = get_game(game_id)
        source = Path(self.folder.name) / (game_id + game.extension)
        source.write_bytes(synthetic_raw(game_id) if raw is None else raw)
        editor = game.create_editor(self.root, self.root)
        with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)), \
                patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            editor.open()
        errors.assert_not_called()
        return editor

    def test_pending_filter_finds_new_values_and_keeps_hidden_edits_for_save(self):
        editor = self.open_editor()
        original = editor.document
        editor.stage_values({'gold': 123456, 'officer_0_attack': 99})
        editor.pending_only.set(True)
        editor.refresh()
        self.assertEqual(set(editor.fields.get_children()), set(editor.changes))
        editor.search.set('123,456')
        self.assertEqual(editor.fields.get_children(), ('gold',))
        self.assertIn('2 pending edits (1 hidden)', editor.field_count.get())
        destination = Path(self.folder.name) / 'edited.dat'
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            editor.save_to(destination)
        errors.assert_not_called()
        self.assertEqual(original.source.read_bytes(), original.raw)
        self.assertEqual(editor.adapter.field_map(editor.document)['gold'].value(editor.document.payload), 123456)
        self.assertEqual(editor.adapter.field_map(editor.document)['officer_0_attack'].value(editor.document.payload), 99)
        self.assertEqual(editor.fields.get_children(), ())
        self.assertEqual((editor.changes, editor.history), ({}, []))

    def test_record_selector_uses_native_identity_and_resets_when_group_changes(self):
        editor = self.open_editor()
        label = next(label for label, key in editor._record_keys.items() if key == ('Officers', 1))
        editor.record.set(label)
        editor.refresh()
        keys = editor.fields.get_children()
        self.assertEqual(set(keys), {'officer_0_attack', 'officer_0_defense', 'officer_0_hp'})
        editor.fields.selection_set(keys)
        editor.max_selected()
        self.assertEqual(set(editor.changes), set(keys))
        editor.group.set('Resources')
        editor.refresh()
        self.assertEqual(editor.record.get(), 'All records')
        self.assertIn('3 pending edits (3 hidden)', editor.field_count.get())
        self.assertEqual(set(editor.changes), set(keys))
        editor.undo()
        self.assertEqual(editor.changes, {})

    def test_reverting_last_visible_pending_row_preserves_other_edits_and_undo(self):
        editor = self.open_editor()
        editor.stage_values({'gold': 123456, 'officer_0_attack': 99})
        editor.pending_only.set(True)
        editor.search.set('gold')
        editor.fields.selection_set('gold')
        editor.revert_selected()
        self.assertEqual(editor.fields.get_children(), ())
        self.assertEqual(editor.changes, {'officer_0_attack': 99})
        self.assertIn('1 pending edits (1 hidden)', editor.field_count.get())
        editor.undo()
        self.assertEqual(editor.fields.get_children(), ('gold',))
        self.assertEqual(editor.changes, {'gold': 123456, 'officer_0_attack': 99})

    def test_opened_value_unstage_rejects_invalid_final_loadout_atomically(self):
        from tests.test_hyrule_fire_emblem_depth import instruction_slot
        editor = self.open_editor('three_houses', instruction_slot())
        first, third = 'character:0:ability:0', 'character:0:ability:2'
        editor.stage_values({first: 240})
        editor.stage_values({third: 2})
        before, history = dict(editor.changes), list(editor.history)
        editor.fields.selection_set(first)
        editor.value.set('2')  # This is the opened value, now occupied in slot 3.
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            editor.apply_selected()
        errors.assert_called_once()
        self.assertEqual(editor.changes, before)
        self.assertEqual(editor.history, history)
        editor.fields.selection_set((first, third))
        editor.revert_selected()
        self.assertEqual(editor.changes, {})
        editor.undo()
        self.assertEqual(editor.changes, before)

    def test_max_failure_and_review_failure_are_reported_without_discarding_edits(self):
        editor = self.open_editor()
        editor.stage_values({'gold': 123456})
        before, history = dict(editor.changes), list(editor.history)
        editor.fields.selection_set('gold')
        with patch.object(editor.backend, 'limit_values', side_effect=SaveError('Rejected native dependency.')), \
                patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            editor.max_selected()
            editor.max_visible()
        self.assertEqual(errors.call_count, 2)
        with patch.object(editor.backend, 'review', side_effect=SaveError('Rejected native dependency.')), \
                patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            editor.review()
        errors.assert_called_once()
        self.assertFalse(any(isinstance(widget, tk.Toplevel) for widget in self.root.winfo_children()))
        self.assertEqual(editor.changes, before)
        self.assertEqual(editor.history, history)

    def test_opening_another_copy_resets_record_and_pending_filters(self):
        editor = self.open_editor()
        label = next(label for label, key in editor._record_keys.items() if key == ('Officers', 1))
        editor.record.set(label)
        editor.pending_only.set(True)
        editor.refresh()
        self.assertEqual(editor.fields.get_children(), ())
        with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(editor.document.source)), \
                patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            editor.open()
        errors.assert_not_called()
        self.assertFalse(editor.pending_only.get())
        self.assertEqual(editor.record.get(), 'All records')
        self.assertGreater(len(editor.fields.get_children()), 100)

    def test_unusual_opened_enum_has_exact_restore_choice_without_granting_it_to_other_records(self):
        from tests.test_dw4hyper_format import procedural_raw, repair_checksum
        raw = bytearray(procedural_raw())
        raw[0xB8 + 8] = 77
        raw[0xB8 + 24 + 8] = 78
        editor = self.open_editor('dw4hyper', repair_checksum(raw))
        key, other = 'officer_0_harness', 'officer_1_harness'
        editor.fields.selection_set(key)
        editor.selected()
        label = '77 · Opened value (preserved)'
        self.assertEqual(editor.choice_value.get(), label)
        editor.choice_value.set('32 · Empty')
        editor.selected_choice()
        editor.apply_selected()
        self.assertEqual(editor.changes, {key: 32})
        self.assertIn(label, editor.value_choice.cget('values'))
        editor.choice_value.set(label)
        editor.selected_choice()
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            editor.apply_selected()
        errors.assert_not_called()
        self.assertEqual(editor.changes, {})
        self.assertEqual(editor.adapter.serialize(editor.document, {}), bytes(repair_checksum(raw)))
        editor.fields.selection_set((key, other))
        editor.selected()
        self.assertNotIn(label, editor.value_choice.cget('values'))
        self.assertNotIn('78 · Opened value (preserved)', editor.value_choice.cget('values'))

    def test_edit_refresh_retains_sort_selection_focus_and_scroll_position(self):
        editor = self.open_editor()
        self.root.geometry('1200x760')
        self.root.deiconify()
        self.root.update()
        editor.sort_fields('slot')
        key = editor.fields.get_children()[-20]
        editor.fields.selection_set(key)
        editor.fields.focus(key)
        editor.fields.see(key)
        self.root.update()
        before = editor.fields.yview()[0]
        order = editor.fields.get_children()
        self.assertGreater(before, 0.5)
        editor.stage_values({'gold': 123456})
        self.root.update()
        self.assertEqual(editor.fields.get_children(), order)
        self.assertEqual(editor.fields.selection(), (key,))
        self.assertEqual(editor.fields.focus(), key)
        self.assertAlmostEqual(editor.fields.yview()[0], before, places=3)

    def test_selected_and_visible_max_restore_opened_maximum_as_one_undo_action(self):
        from dataclasses import replace
        from koei_editor.shared import verified_editor as backend
        from tests.test_verified_snapshot_review import reseed
        document = backend.decode(synthetic_raw('dw8xl'), 'dw8xl')
        field = backend.field_map(document)['gold']
        payload = bytearray(document.payload)
        payload[field.offset:field.offset + field.size] = field.maximum.to_bytes(field.size, 'little')
        raw = reseed(replace(document, payload=bytes(payload)), document.seed)
        editor = self.open_editor(raw=raw)
        editor.stage_values({'gold': 100, 'officer_0_attack': 99})
        before = dict(editor.changes)
        editor.fields.selection_set('gold')
        editor.max_selected()
        self.assertEqual(editor.changes, {'officer_0_attack': 99})
        editor.undo()
        self.assertEqual(editor.changes, before)
        editor.search.set('gold')
        self.assertEqual(editor.fields.get_children(), ('gold',))
        editor.max_visible()
        self.assertEqual(editor.changes, {'officer_0_attack': 99})
        self.assertIn('1 pending edits (1 hidden)', editor.field_count.get())
        self.assertEqual(editor.document.source.read_bytes(), raw)

    def test_max_restores_higher_original_targets_and_excludes_nonmaxable_fields(self):
        import struct
        from koei_editor.games.wo4 import parser as backend
        from tests.test_wo4_pc import generated_raw, repack
        document = backend.decode(generated_raw())
        payload = bytearray(document.payload)
        struct.pack_into('<I', payload, backend.SYSTEM_GLOBAL + 0xCC, 123456789)
        struct.pack_into('<H', payload, backend.SYSTEM_GLOBAL + 0xD4, 999)
        raw = repack(payload)
        editor = self.open_editor(backend.GAME_ID, raw)
        unusual = 'officer_002_skill_points'
        editor.stage_values({'gems': 100, 'crystals': 10, unusual: 10, 'skill_orbs': 5})
        before = dict(editor.changes)
        editor.fields.selection_set(tuple(before))
        editor.max_selected()
        # Max restores exact higher opened values and the crystal maximum,
        # while metadata keeps the nonmaxable Skill Orb reduction pending.
        self.assertEqual(editor.changes, {'skill_orbs': 5})
        editor.undo()
        self.assertEqual(editor.changes, before)
        history = list(editor.history)
        editor.search.set('gems')
        self.assertEqual(editor.fields.get_children(), ('gems',))
        editor.max_visible()
        self.assertEqual(editor.changes, {'crystals': 10, unusual: 10, 'skill_orbs': 5})
        editor.undo()
        self.assertEqual(editor.changes, before)
        self.assertEqual(editor.history, history)
        editor.search.set('')
        editor.fields.selection_set('skill_orbs')
        # Metadata stays authoritative even if a backend returns a valid
        # original assignment for a field explicitly excluded from bulk Max.
        with patch.object(backend, 'limit_values', return_value={'skill_orbs': 7}):
            editor.max_selected()
        self.assertEqual(editor.changes, before)
        self.assertEqual(editor.history, history)
        self.assertEqual(editor.document.source.read_bytes(), raw)


if __name__ == '__main__':
    unittest.main()
