"""Safe handoff from read-only comparisons to qualified transfer previews."""
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.game_registry import get_game
from koei_editor.shared.comparison_gui import ComparisonWorkspace
from koei_editor.shared.transfer_gui import TransferDialog
from tests.test_origins_parser import fixture as origins_fixture


class ComparisonDefinitionIdentityTests(unittest.TestCase):
    def test_same_storage_with_changed_choice_metadata_is_a_definition_change(self):
        from dataclasses import dataclass
        from types import MappingProxyType
        from koei_editor.games.origins import origins_parser
        from koei_editor.shared import save_comparison

        @dataclass(frozen=True)
        class ChoiceField(origins_parser.Field):
            choices: tuple = ()

        left_raw, right_raw = origins_fixture(gold=3456), origins_fixture(gold=7890)
        left = origins_parser.decode(left_raw)
        right = origins_parser.decode(right_raw)
        left_fields = origins_parser.field_map(left)
        right_fields = dict(origins_parser.field_map(right))
        original = right_fields['gold']
        right_fields['gold'] = ChoiceField(
            original.id, original.label, original.offset, original.size,
            original.maximum, original.group, original.slot, original.minimum,
            original.maxable, ('unspent', 'reserved'))
        self.assertEqual((left_fields['gold'].offset, left_fields['gold'].size),
                         (right_fields['gold'].offset, right_fields['gold'].size))
        with patch.object(origins_parser, 'field_map',
                          side_effect=(left_fields, MappingProxyType(right_fields))):
            compared = save_comparison.compare_documents('origins', left, right)
        gold = next(row for row in compared.rows if row.id == 'gold')
        self.assertEqual((gold.left, gold.right), (3456, 7890))
        self.assertEqual(gold.status, 'definition_changed')


class ComparisonTransferExperienceTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.area = tempfile.TemporaryDirectory()
        self.addCleanup(self.area.cleanup)
        self.folder = Path(self.area.name)

    def editor_for(self, game_id, target_path):
        editor = get_game(game_id).create_editor(self.root, self.root)
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            self.assertTrue(editor.open_path(target_path))
        errors.assert_not_called()
        return editor

    def workspace(self, editor, game_id, first, second):
        workspace = ComparisonWorkspace(
            self.root, self.root, initial_game_id=game_id,
            initial_first=str(first), target_editor=editor,
        )
        workspace.second.set(str(second))
        return workspace

    def finish(self, workspace):
        deadline = time.monotonic() + 10
        while workspace.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertFalse(workspace.busy, 'Comparison worker did not finish.')
        self.root.update()

    @staticmethod
    def comparison_row(workspace, field_id):
        for identity in workspace.table.get_children():
            row = workspace.prepared.rows[int(identity)]
            if row.id == field_id:
                return identity
        raise AssertionError(f'Comparison did not show {field_id}.')

    def test_comparison_preselects_only_catalogue_approved_fields_and_applies_one_undo(self):
        from koei_editor.games.origins import origins_parser

        target_raw = origins_fixture()
        target_document = origins_parser.decode(target_raw)
        peace = origins_parser.field_map(target_document)['peace_0']
        peace_value = peace.value(target_document.payload)
        source_raw = origins_parser.serialize(target_document, {
            'gold': 12345,
            'peace_0': peace_value + 1,
        })
        target_path, source_path = self.folder / 'target.dat', self.folder / 'source.dat'
        target_path.write_bytes(target_raw)
        source_path.write_bytes(source_raw)
        editor = self.editor_for('origins', target_path)
        workspace = self.workspace(editor, 'origins', target_path, source_path)
        self.assertEqual(workspace._games[workspace.game.get()], 'origins')
        self.assertEqual(workspace.first.get(), str(target_path))

        workspace.compare()
        self.finish(workspace)
        workspace.table.selection_set((
            self.comparison_row(workspace, 'gold'),
            self.comparison_row(workspace, 'peace_0'),
        ))
        transfer = workspace.open_selective_transfer()
        self.assertIsInstance(transfer, TransferDialog)
        approved = {choice.id for choice in transfer.available.choices}
        self.assertIn('gold', approved)
        self.assertNotIn('peace_0', approved)
        self.assertEqual(transfer.selected, {'gold'})
        self.assertIn('peace_0', str([transfer.exclusions.item(key, 'values')
                                     for key in transfer.exclusions.get_children()]))
        self.assertTrue(transfer.summary.get())
        self.assertEqual(editor.changes, {})

        with patch('koei_editor.shared.transfer_gui.messagebox.showerror') as errors:
            self.assertTrue(transfer.prepare_preview())
            errors.assert_not_called()
        self.assertEqual(dict(transfer.plan.result), {'gold': 12345})
        self.assertEqual(editor.changes, {})
        self.assertTrue(transfer.apply_preview())
        self.assertEqual(editor.changes, {'gold': 12345})
        self.assertEqual(editor.history, [{}])
        self.assertEqual(target_path.read_bytes(), target_raw)
        self.assertEqual(source_path.read_bytes(), source_raw)
        self.assertEqual(editor.backup.read_bytes(), target_raw)
        editor.undo()
        self.assertEqual((editor.changes, editor.history), ({}, []))
        self.assertEqual(target_path.read_bytes(), target_raw)
        self.assertEqual(source_path.read_bytes(), source_raw)

    def test_comparison_transfer_allows_owned_equipment_reference_with_preview_label(self):
        from koei_editor.games.wo3u import wo3u_equipment
        from tests.test_wo3u_mounts import mount_raw

        target_raw = mount_raw()
        source = bytearray(target_raw)
        source[wo3u_equipment.MOUNT_LOADOUT_OFFSETS[0]] = 3
        source_raw = bytes(source)
        target_path, source_path = self.folder / 'target.bin', self.folder / 'source.bin'
        target_path.write_bytes(target_raw)
        source_path.write_bytes(source_raw)
        editor = self.editor_for('wo3u', target_path)
        workspace = self.workspace(editor, 'wo3u', target_path, source_path)
        workspace.compare()
        self.finish(workspace)
        workspace.table.selection_set(self.comparison_row(workspace, 'mount_loadout_0'))

        transfer = workspace.open_selective_transfer()
        self.assertEqual(transfer.selected, {'mount_loadout_0'})
        self.assertTrue(transfer.prepare_preview())
        self.assertEqual(dict(transfer.plan.result), {'mount_loadout_0': 3})
        preview_values = [transfer.preview.item(key, 'values')
                          for key in transfer.preview.get_children()]
        self.assertIn('Owned mount item ID 31', str(preview_values))
        self.assertEqual(editor.changes, {})
        self.assertTrue(transfer.apply_preview())
        self.assertEqual(editor.changes, {'mount_loadout_0': 3})
        self.assertEqual(editor.history, [{}])
        self.assertEqual(target_path.read_bytes(), target_raw)
        self.assertEqual(source_path.read_bytes(), source_raw)
        self.assertEqual(editor.backup.read_bytes(), target_raw)
        editor.undo()
        self.assertEqual((editor.changes, editor.history), ({}, []))

    def test_unsupported_comparable_profile_keeps_read_only_comparison_without_handoff(self):
        from koei_editor.shared import save_transfer
        from tests.test_dw4hyper_format import procedural_raw

        raw = procedural_raw()
        target_path = self.folder / 'dw4hyper_target.dat'
        target_path.write_bytes(raw)
        editor = self.editor_for('dw4hyper', target_path)
        workspace = ComparisonWorkspace(
            self.root, self.root, initial_game_id='dw4hyper',
            initial_first=str(target_path), target_editor=editor)
        self.assertFalse(save_transfer.supports_transfer(editor.adapter))
        self.assertEqual(workspace._games[workspace.game.get()], 'dw4hyper')
        self.assertEqual(workspace.transfer_button.winfo_manager(), '')
        self.assertEqual(str(workspace.compare_button['state']), 'normal')

    def test_stale_comparison_sources_and_changed_target_session_do_not_open_transfer(self):
        target_path, source_path = self.folder / 'target.dat', self.folder / 'source.dat'
        target_raw, source_raw = origins_fixture(), origins_fixture(gold=9999)
        target_path.write_bytes(target_raw)
        source_path.write_bytes(source_raw)
        editor = self.editor_for('origins', target_path)
        workspace = self.workspace(editor, 'origins', target_path, source_path)
        workspace.compare()
        self.finish(workspace)
        workspace.table.selection_set(self.comparison_row(workspace, 'gold'))

        source_path.write_bytes(origins_fixture(gold=7777))
        with patch('koei_editor.shared.comparison_gui.messagebox.showerror') as errors:
            self.assertIsNone(workspace.open_selective_transfer())
        errors.assert_called_once()
        self.assertEqual((editor.changes, editor.history), ({}, []))
        self.assertEqual(target_path.read_bytes(), target_raw)

        # Replacing the donor after comparison's path check but before the
        # transfer dialog reads it must fail the handoff's expected digest.
        source_path.write_bytes(source_raw)
        workspace.compare()
        self.finish(workspace)
        workspace.table.selection_set(self.comparison_row(workspace, 'gold'))
        from koei_editor.shared import comparison_gui
        validate_sources = comparison_gui.backend.validate_sources
        def validate_then_replace(prepared):
            validate_sources(prepared)
            source_path.write_bytes(origins_fixture(gold=7777))
        with patch('koei_editor.shared.comparison_gui.backend.validate_sources',
                   side_effect=validate_then_replace), \
                patch('koei_editor.shared.transfer_gui.messagebox.showerror') as errors:
            transfer = workspace.open_selective_transfer()
        self.assertIsInstance(transfer, TransferDialog)
        self.assertIsNone(transfer.source)
        self.assertIsNone(transfer.available)
        self.assertEqual(transfer.selected, set())
        self.assertEqual(transfer.choices.get_children(), ())
        self.assertEqual(str(transfer.preview_button['state']), 'disabled')
        errors.assert_called_once()
        transfer.close()
        self.assertEqual((editor.changes, editor.history), ({}, []))
        self.assertEqual(target_path.read_bytes(), target_raw)

        # A fresh comparison for a previous source must also be invalid after the
        # retained editor has opened a different target copy.
        source_path.write_bytes(source_raw)
        workspace.compare()
        self.finish(workspace)
        workspace.table.selection_set(self.comparison_row(workspace, 'gold'))
        other_target = self.folder / 'other.dat'
        other_raw = origins_fixture(gold=8000)
        other_target.write_bytes(other_raw)
        self.assertTrue(editor.open_path(other_target))
        with patch('koei_editor.shared.comparison_gui.messagebox.showerror') as errors:
            self.assertIsNone(workspace.open_selective_transfer())
        errors.assert_called_once()
        self.assertEqual((editor.changes, editor.history), ({}, []))
        self.assertEqual(other_target.read_bytes(), other_raw)
        self.assertEqual(source_path.read_bytes(), source_raw)

    def test_application_binds_comparison_to_active_open_editor_and_rebinds(self):
        from koei_editor.application import Application
        from tests.test_wo3u_mounts import mount_raw

        first_raw = origins_fixture()
        donor_raw = origins_fixture(gold=7777)
        first_path, donor_path = self.folder / 'origins_target.dat', self.folder / 'origins_donor.dat'
        first_path.write_bytes(first_raw)
        donor_path.write_bytes(donor_raw)
        app = Application(self.root, persist_preferences=False,
                          preferences_path=self.folder / 'preferences.json')
        origins_editor = app.select_game('origins')
        self.assertTrue(origins_editor.open_path(first_path))
        app.show_comparison()
        workspace = app.comparison
        self.assertIs(workspace.target_editor, origins_editor)
        self.assertEqual(workspace.first.get(), str(first_path))
        workspace.second.set(str(donor_path))
        workspace.compare()
        self.finish(workspace)
        self.assertIsNotNone(workspace.prepared)

        # Switching to an unopened scalar session clears the transfer target
        # and invalidates rows bound to the previous destination snapshot.
        unopened = app.select_game('wo3u')
        self.root.update()
        self.assertIsNone(workspace.target_editor)
        self.assertIsNone(workspace.prepared)

        wo3u_path = self.folder / 'wo3u_target.bin'
        wo3u_path.write_bytes(mount_raw())
        self.assertTrue(unopened.open_path(wo3u_path))
        self.assertIs(app.select_game('wo3u'), unopened)
        self.root.update()
        self.assertIs(workspace.target_editor, unopened)
        self.assertEqual(workspace.first.get(), str(wo3u_path))
        self.assertEqual(workspace._games[workspace.game.get()], 'wo3u')
        self.assertIsNone(workspace.prepared)


if __name__ == '__main__':
    unittest.main()
