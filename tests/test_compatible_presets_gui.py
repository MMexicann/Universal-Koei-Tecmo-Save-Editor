"""Actual management controls stage reviewed resource batches, never game files."""
from dataclasses import replace
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from koei_editor.game_registry import get_game
from koei_editor.shared import compatible_presets as presets
from koei_editor.shared.compatible_preset_gui import CompatiblePresetWorkspace
from koei_editor.shared.preset_library import PresetLibrary
from tests.test_origins_parser import fixture


class CompatiblePresetGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.root.destroy)
        self.root.geometry('1400x950')
        self.area = tempfile.TemporaryDirectory()
        self.addCleanup(self.area.cleanup)
        self.folder = Path(self.area.name).resolve()
        self.editors = []
        for name, gold in (('source', 3456), ('target', 7777)):
            path = self.folder / (name + '.dat')
            path.write_bytes(fixture(gold=gold))
            host = ttk.Frame(self.root)
            editor = get_game('origins').create_editor(self.root, host)
            with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                self.assertTrue(editor.open_path(path))
                errors.assert_not_called()
            self.editors.append(editor)
        self.source, self.target = self.editors
        self.sessions = [('Source', self.source), ('Target', self.target)]
        self.library = PresetLibrary(self.folder / 'library')
        with patch('koei_editor.shared.compatible_preset_gui.PresetLibrary', return_value=self.library):
            self.workspace = CompatiblePresetWorkspace(self.root, self.root, lambda: tuple(self.sessions))
        self.workspace.frame.pack(fill='both', expand=True)
        self.source.stage_values({'gold': 12345, 'skill_points': 456})
        self.entry = self.workspace.create_from_staged('Resource plan')
        self.workspace.target.set('Target')
        self.root.update()

    def assert_sources_preserved(self):
        for editor in self.editors:
            self.assertEqual(editor.document.source.read_bytes(), editor.document.raw)
            self.assertEqual(editor.backup.read_bytes(), editor.document.raw)

    def preview(self):
        with patch('koei_editor.shared.compatible_preset_gui.messagebox.showerror') as errors:
            self.assertTrue(self.workspace.prepare_preview())
            errors.assert_not_called()

    def test_selected_bulk_preview_apply_one_undo_preserves_hidden_pending_and_sources(self):
        self.target.stage_values({'dlc_skill_points': 77})
        previous, history = dict(self.target.changes), list(self.target.history)
        self.workspace.assignments.selection_set('gold')
        self.root.update()
        self.preview()
        self.assertEqual(set(row.field.id for row in self.workspace._plan.rows), {'gold', 'dlc_skill_points'})
        self.assertEqual(len(self.workspace.preview.get_children()), 2)
        self.assertEqual(self.target.changes, previous)
        with patch('koei_editor.shared.compatible_preset_gui.messagebox.showerror') as errors:
            self.assertTrue(self.workspace.apply_preview())
            errors.assert_not_called()
        self.assertEqual(self.target.changes, {'gold': 12345, 'dlc_skill_points': 77})
        self.assertEqual(self.target.history, history + [previous])
        self.target.undo()
        self.assertEqual(self.target.changes, previous)
        self.assertEqual(self.target.history, history)
        self.assert_sources_preserved()

    def test_search_themes_and_source_bound_action_do_not_mutate_game_state(self):
        previous = [(dict(editor.changes), list(editor.history)) for editor in self.editors]
        self.workspace.search.set('resource origins')
        self.assertEqual(len(self.workspace.catalog.get_children()), 1)
        self.workspace.search.set('missing')
        self.assertEqual(self.workspace.catalog.get_children(), ())
        self.workspace.search.set('')
        self.workspace.catalog.selection_set(self.entry.id)
        self.workspace._catalog_selected()
        for name in ('Dark', 'Light'):
            self.target.apply_theme(name)
            from koei_editor.shared.appearance import THEMES
            self.workspace.apply_theme(THEMES[name])
            self.root.update_idletasks()
        with patch('koei_editor.shared.preset_gui.open_presets') as opened:
            self.workspace.open_source_presets()
            opened.assert_called_once_with(self.target)
        self.assertEqual([(dict(editor.changes), list(editor.history)) for editor in self.editors], previous)
        self.assert_sources_preserved()

    def test_assignment_or_target_change_requires_fresh_complete_preview(self):
        self.preview()
        self.workspace.assignments.selection_set('gold')
        self.root.update()
        self.assertIsNone(self.workspace._plan)
        with patch('koei_editor.shared.compatible_preset_gui.messagebox.showerror') as errors:
            self.assertFalse(self.workspace.apply_preview())
            errors.assert_called_once()
        self.preview()
        self.workspace.target.set('Source')
        self.assertIsNone(self.workspace._plan)
        self.assertEqual(self.target.changes, {})
        self.assert_sources_preserved()

    def test_stale_pending_or_source_rejects_apply_without_losing_edits(self):
        self.preview()
        self.target.stage_values({'dlc_skill_points': 88})
        previous, history = dict(self.target.changes), list(self.target.history)
        with patch('koei_editor.shared.compatible_preset_gui.messagebox.showerror') as errors:
            self.assertFalse(self.workspace.apply_preview())
            errors.assert_called_once()
        self.assertEqual((self.target.changes, self.target.history), (previous, history))
        self.preview()
        self.target.document.source.write_bytes(self.source.document.raw)
        with patch('koei_editor.shared.compatible_preset_gui.messagebox.showerror') as errors:
            self.assertFalse(self.workspace.apply_preview())
            errors.assert_called_once()
        self.assertEqual((self.target.changes, self.target.history), (previous, history))

    def test_multi_file_import_export_and_existing_metadata_preservation(self):
        second = replace(self.entry.preset, name='Second resource plan')
        incoming = self.folder / 'incoming'
        incoming.mkdir()
        first_path = presets.export(self.entry.preset, incoming / 'one')
        second_path = presets.export(second, incoming / 'two')
        with patch('koei_editor.shared.compatible_preset_gui.filedialog.askopenfilenames',
                   return_value=(str(first_path), str(second_path))):
            self.workspace.import_dialog()
        self.assertEqual(len(self.library.scan().entries), 2)
        entries = self.workspace.entries
        destination = self.folder / 'exported'
        destination.mkdir()
        self.workspace.catalog.selection_set(tuple(entry.id for entry in entries))
        self.workspace._catalog_selected()
        with patch('koei_editor.shared.compatible_preset_gui.filedialog.askdirectory', return_value=str(destination)):
            self.assertTrue(self.workspace.export_dialog())
        actual = tuple(destination.iterdir())
        self.assertEqual(len(actual), 2)
        self.assertEqual({presets.load(path).name for path in actual}, {'Resource plan', 'Second resource plan'})
        originals = {path: path.read_bytes() for path in actual}
        with self.assertRaises(FileExistsError):
            self.library.export(entries[0], actual[0])
        self.assertEqual({path: path.read_bytes() for path in actual}, originals)
        self.assert_sources_preserved()

    def test_missing_target_local_metadata_change_and_lifecycle(self):
        self.entry.path.write_bytes(presets.dumps(replace(self.entry.preset, name='Foreign changed metadata')))
        with patch('koei_editor.shared.compatible_preset_gui.messagebox.showerror') as errors:
            self.assertFalse(self.workspace.prepare_preview())
            errors.assert_called_once()
        self.sessions.clear()
        self.workspace.on_show()
        self.assertEqual(tuple(self.workspace.target_selector.cget('values')), ())
        self.assertEqual(self.workspace.target.get(), '')
        self.assertFalse(self.workspace.has_pending_work())
        self.workspace.close()
        self.assertIsNone(self.workspace._plan)
        self.assert_sources_preserved()

    def test_modal_create_displays_exclusions_and_only_explicit_resource_selection_saves(self):
        self.workspace.target.set('Source')
        # Existing mapped bond fields are not approved for cross-save transfer.
        mapping = self.source.adapter.field_map(self.source.document)
        unsafe = next((field for field in mapping.values() if field.id.startswith('peace_')), None)
        self.assertIsNotNone(unsafe)
        self.source.stage_values({unsafe.id: min(unsafe.maximum, max(0, unsafe.value(self.source.document.payload) - 1))})
        window = self.workspace.create_dialog()
        self.assertIsInstance(window, tk.Toplevel)
        def tables(widget):
            return [widget] if isinstance(widget, ttk.Treeview) else [item for child in widget.winfo_children() for item in tables(child)]
        table = tables(window)[0]
        self.assertIn('Excluded:', table.item(unsafe.id, 'values')[2])
        self.assertNotIn(unsafe.id, table.selection())
        window.destroy()
        entry = self.workspace.create_from_staged('Only gold', ('gold',))
        self.assertEqual(tuple(edit.field for edit in entry.preset.edits), ('gold',))
        self.assertIn(unsafe.id, self.source.changes)
        self.assert_sources_preserved()

    def test_bulk_target_selection_preview_apply_and_individual_undo(self):
        self.target.stage_values({'dlc_skill_points': 77})
        self.workspace.assignments.selection_set('gold')
        dialog = self.workspace.bulk_dialog()
        dialog.targets.selection_set(('0', '1'))
        self.root.update()
        with patch('koei_editor.shared.compatible_preset_gui.messagebox.showerror') as errors:
            self.assertTrue(dialog.prepare())
            self.assertEqual(len(dialog.batch.targets), 2)
            self.assertEqual(len(dialog.preview.get_children()), 4)
            self.assertEqual(self.target.changes, {'dlc_skill_points': 77})
            self.assertTrue(dialog.apply())
            errors.assert_not_called()
        self.assertEqual(self.target.changes, {'gold': 12345, 'dlc_skill_points': 77})
        self.target.undo()
        self.assertEqual(self.target.changes, {'dlc_skill_points': 77})
        self.assert_sources_preserved()
        dialog.window.destroy()

    def test_bulk_stale_target_and_selection_changes_require_fresh_preview(self):
        dialog = self.workspace.bulk_dialog()
        dialog.targets.selection_set('1')
        self.root.update()
        with patch('koei_editor.shared.compatible_preset_gui.messagebox.showerror') as errors:
            self.assertTrue(dialog.prepare())
            self.target.stage_values({'dlc_skill_points': 77})
            self.assertFalse(dialog.apply())
            self.assertEqual(self.target.changes, {'dlc_skill_points': 77})
            self.assertTrue(dialog.prepare())
            dialog.targets.selection_set('0')
            self.root.update()
            self.assertIsNone(dialog.batch)
            self.assertFalse(dialog.apply())
            self.assertEqual(errors.call_count, 2)
        self.assert_sources_preserved()
        dialog.window.destroy()

    def test_independent_target_windows_bulk_apply_save_as_and_close_safety(self):
        paths = tuple(self.folder / name for name in ('third.dat', 'fourth.dat'))
        originals = {}
        for index, path in enumerate(paths):
            originals[path] = fixture(gold=8000 + index)
            path.write_bytes(originals[path])
        from koei_editor.shared.appearance import THEMES
        self.workspace.apply_theme(THEMES['Dark'])
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            copies = self.workspace.open_target_paths('origins', paths)
            errors.assert_not_called()
        self.assertEqual(len(copies), 2)
        self.assertEqual(len(self.workspace._sessions), 4)
        self.assertTrue(all(editor.theme_name.get() == 'Dark' for editor in copies))
        dialog = self.workspace.bulk_dialog()
        dialog.targets.selection_set(('2', '3'))
        self.root.update()
        self.assertTrue(dialog.prepare())
        self.assertTrue(dialog.apply())
        dialog.window.destroy()
        self.assertTrue(self.workspace.has_pending_work())
        self.assertFalse(self.workspace.busy)
        with patch('koei_editor.shared.verified_gui.messagebox.askyesno', return_value=False):
            self.assertFalse(self.workspace.dirty_ok())
            self.assertFalse(self.workspace.close_target(1))
        self.assertEqual(len(self.workspace._copy_sessions), 2)
        output = self.folder / 'third-edited.dat'
        with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(output)):
            copies[0].save_as()
        reopened = copies[0].adapter.read_save(output)
        self.assertEqual(copies[0].adapter.field_map(reopened)['gold'].value(reopened.payload), 12345)
        self.assertTrue(self.workspace.close_target(1))
        copies[1].undo()
        self.assertFalse(self.workspace.has_pending_work())
        self.assertTrue(self.workspace.close_target(2))
        self.assertEqual(self.workspace._copy_sessions, {})
        self.assertEqual(len(self.workspace._sessions), 2)
        self.assertEqual({path: path.read_bytes() for path in paths}, originals)

    def test_target_open_rejects_duplicate_and_foreign_copies(self):
        with self.assertRaisesRegex(Exception, 'already open'):
            self.workspace.open_target_paths('origins', (self.source.document.source,))
        foreign = self.folder / 'foreign.dat'
        foreign.write_bytes(b'foreign native format')
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            with self.assertRaisesRegex(Exception, 'could not be opened'):
                self.workspace.open_target_paths('origins', (foreign,))
            errors.assert_called_once()
        self.assertEqual(self.workspace._copy_sessions, {})
        self.assert_sources_preserved()


if __name__ == '__main__':
    unittest.main()
