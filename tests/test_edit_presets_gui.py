"""Live Tk preset review, deliberate apply, one-step Undo and failure retention."""
from dataclasses import replace
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.game_registry import get_game
from koei_editor.shared import edit_presets
from koei_editor.shared.preset_gui import open_presets
from tests.test_origins_parser import fixture


class EditPresetGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.root.destroy)
        self.root.withdraw()
        self.area = tempfile.TemporaryDirectory()
        self.addCleanup(self.area.cleanup)
        self.folder = Path(self.area.name)
        self.source = self.folder / 'SLOT0000.dat'
        self.source.write_bytes(fixture())
        self.editor = get_game('origins').create_editor(self.root, self.root)
        with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(self.source)), \
                patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            self.editor.open()
        errors.assert_not_called()
        self.document = self.editor.document
        self.preset = edit_presets.create(self.editor.adapter, self.document, {'gold': 12345}, 'Officer plan')
        self.path = edit_presets.export(self.preset, self.editor.adapter, self.document, self.folder / 'plan')
        self.dialog = open_presets(self.editor)
        self.root.update()

    def load(self):
        with patch('koei_editor.shared.preset_gui.messagebox.showerror') as errors:
            result = self.dialog.load_path(self.path)
        errors.assert_not_called()
        self.assertTrue(result)

    def test_import_previews_all_edits_and_search_never_changes_pending_map(self):
        self.editor.stage_values({'skill_points': 456})
        original = (dict(self.editor.changes), list(self.editor.history))
        self.load()
        self.assertEqual(len(self.dialog.tree.get_children()), 2)
        self.assertIn('12,345', str([self.dialog.tree.item(key, 'values') for key in self.dialog.tree.get_children()]))
        self.dialog.query.set('12345')
        self.assertEqual(len(self.dialog.tree.get_children()), 1)
        self.assertEqual(self.dialog.count.get(), '1 of 2 fields')
        self.assertEqual((self.editor.changes, self.editor.history), original)
        self.assertEqual(self.source.read_bytes(), self.document.raw)

    def test_apply_is_deliberate_atomic_and_one_undo_action(self):
        self.editor.stage_values({'skill_points': 456})
        previous, history = dict(self.editor.changes), list(self.editor.history)
        self.load()
        self.assertEqual(self.editor.changes, previous)
        with patch('koei_editor.shared.preset_gui.messagebox.showerror') as errors:
            self.assertTrue(self.dialog.apply_preview())
        errors.assert_not_called()
        self.assertEqual(self.editor.changes, {'gold': 12345, 'skill_points': 456})
        self.assertEqual(self.editor.history, history + [previous])
        self.assertIn('Use Save As', self.editor.status.get())
        self.editor.undo()
        self.assertEqual(self.editor.changes, previous)
        self.assertEqual(self.editor.history, history)
        self.assertEqual(self.source.read_bytes(), self.document.raw)

    def test_cancel_import_and_close_preserve_existing_preview_and_all_edits(self):
        self.editor.stage_values({'skill_points': 456})
        self.load()
        plan = self.dialog.plan
        original = (dict(self.editor.changes), list(self.editor.history))
        with patch('koei_editor.shared.preset_gui.filedialog.askopenfilename', return_value=''):
            self.dialog.import_preset()
        self.assertIs(self.dialog.plan, plan)
        self.dialog.close()
        self.assertEqual((self.editor.changes, self.editor.history), original)

    def test_bad_import_clears_older_preview_without_touching_edits_or_history(self):
        self.editor.stage_values({'skill_points': 456})
        self.load()
        original = (dict(self.editor.changes), list(self.editor.history))
        bad = self.folder / 'bad.edits.json'
        bad.write_text('{"schema":1,"schema":2}', encoding='utf-8')
        with patch('koei_editor.shared.preset_gui.messagebox.showerror') as errors:
            self.assertFalse(self.dialog.load_path(bad))
        errors.assert_called_once()
        self.assertIsNone(self.dialog.plan)
        self.assertEqual(str(self.dialog.apply_button['state']), 'disabled')
        self.assertEqual((self.editor.changes, self.editor.history), original)

    def test_changing_pending_edits_after_preview_requires_a_new_review(self):
        self.load()
        self.editor.stage_values({'skill_points': 456})
        original = (dict(self.editor.changes), list(self.editor.history))
        with patch('koei_editor.shared.preset_gui.messagebox.showerror') as errors:
            self.assertFalse(self.dialog.apply_preview())
        self.assertIn('Pending edits changed', str(errors.call_args))
        self.assertEqual((self.editor.changes, self.editor.history), original)

    def test_source_change_after_preview_does_not_stage_or_write(self):
        self.editor.stage_values({'skill_points': 456})
        self.load()
        original = (dict(self.editor.changes), list(self.editor.history))
        changed = fixture(gold=3500)
        self.source.write_bytes(changed)
        with patch('koei_editor.shared.preset_gui.messagebox.showerror') as errors:
            self.assertFalse(self.dialog.apply_preview())
        errors.assert_called_once()
        self.assertEqual((self.editor.changes, self.editor.history), original)
        self.assertEqual(self.source.read_bytes(), changed)

    def test_refresh_failure_retains_complete_pending_state_and_undo_history(self):
        self.editor.stage_values({'skill_points': 456})
        self.load()
        original = (dict(self.editor.changes), list(self.editor.history))
        with patch.object(self.editor, 'refresh', side_effect=RuntimeError('Presentation failed.')), \
                patch('koei_editor.shared.preset_gui.messagebox.showerror') as errors:
            self.assertFalse(self.dialog.apply_preview())
        errors.assert_called_once()
        self.assertEqual((self.editor.changes, self.editor.history), original)
        self.assertEqual(self.source.read_bytes(), self.document.raw)

    def test_source_change_during_pending_commit_rolls_back_history_and_display(self):
        self.editor.stage_values({'skill_points': 456})
        self.load()
        original = (dict(self.editor.changes), list(self.editor.history))
        accept = self.editor._accept_pending
        mutations = []
        def mutate(result):
            accept(result)
            self.source.write_bytes(fixture(gold=3500))
            mutations.append(True)
        with patch.object(self.editor, '_accept_pending', side_effect=mutate), \
                patch('koei_editor.shared.preset_gui.messagebox.showerror') as errors:
            self.assertFalse(self.dialog.apply_preview())
        self.assertEqual(len(mutations), 1)
        errors.assert_called_once()
        self.assertEqual((self.editor.changes, self.editor.history), original)
        self.assertNotIn('12,345', str(self.editor.fields.item('gold', 'values')))
        self.assertIn('retained', self.editor.status.get())
        self.assertIsNone(self.dialog.plan)

    def test_noop_import_never_adds_an_undo_snapshot(self):
        self.editor.stage_values({'gold': 12345})
        self.load()
        self.assertEqual(str(self.dialog.apply_button['state']), 'disabled')
        self.assertIn('0 pending values change', self.dialog.summary.get())
        original = (dict(self.editor.changes), list(self.editor.history))
        self.assertTrue(self.dialog.apply_preview())
        self.assertEqual((self.editor.changes, self.editor.history), original)

    def test_export_completes_suffix_includes_hidden_fields_and_reports_actual_filename(self):
        self.editor.stage_values({'gold': 100, 'skill_points': 456})
        self.editor.search.set('nothing-visible')
        self.editor.refresh()
        self.assertFalse(self.editor.fields.get_children())
        original = (dict(self.editor.changes), list(self.editor.history))
        destination = self.folder / 'APP.BIN'
        with patch('koei_editor.shared.preset_gui.simpledialog.askstring', return_value='Hidden fields'), \
                patch('koei_editor.shared.preset_gui.filedialog.asksaveasfilename', return_value=str(destination)), \
                patch('koei_editor.shared.preset_gui.messagebox.showerror') as errors:
            self.assertTrue(self.dialog.export_staged())
        errors.assert_not_called()
        actual = self.folder / 'APP.BIN.edits.json'
        self.assertEqual({edit.field: edit.value for edit in edit_presets.load(actual).edits}, original[0])
        self.assertIn(actual.name, self.editor.status.get())
        self.assertIn(actual.name, self.dialog.summary.get())
        self.assertFalse(destination.exists())
        self.assertEqual((self.editor.changes, self.editor.history), original)
        self.assertEqual(self.source.read_bytes(), self.document.raw)

    def test_export_cancel_and_existing_file_preserve_original_state(self):
        self.editor.stage_values({'gold': 100})
        original = (dict(self.editor.changes), list(self.editor.history))
        with patch('koei_editor.shared.preset_gui.simpledialog.askstring', return_value=None), \
                patch('koei_editor.shared.preset_gui.filedialog.asksaveasfilename') as choose:
            self.assertFalse(self.dialog.export_staged())
        choose.assert_not_called()
        with patch('koei_editor.shared.preset_gui.simpledialog.askstring', return_value='Cancelled'), \
                patch('koei_editor.shared.preset_gui.filedialog.asksaveasfilename', return_value=''):
            self.assertFalse(self.dialog.export_staged())
        existing = self.path.read_bytes()
        with patch('koei_editor.shared.preset_gui.simpledialog.askstring', return_value='Existing'), \
                patch('koei_editor.shared.preset_gui.filedialog.asksaveasfilename', return_value=str(self.path)), \
                patch('koei_editor.shared.preset_gui.messagebox.showerror') as errors:
            self.assertFalse(self.dialog.export_staged())
        errors.assert_called_once()
        self.assertEqual(self.path.read_bytes(), existing)
        self.assertEqual((self.editor.changes, self.editor.history), original)

    def test_export_rejects_session_changes_while_file_dialog_is_open(self):
        self.editor.stage_values({'gold': 100})
        destination = self.folder / 'stale'
        def choose(**_kwargs):
            self.editor.stage_values({'skill_points': 456})
            return str(destination)
        with patch('koei_editor.shared.preset_gui.simpledialog.askstring', return_value='Stale'), \
                patch('koei_editor.shared.preset_gui.filedialog.asksaveasfilename', side_effect=choose), \
                patch('koei_editor.shared.preset_gui.messagebox.showerror') as errors:
            self.assertFalse(self.dialog.export_staged())
        self.assertIn('editor changed', str(errors.call_args))
        self.assertFalse(edit_presets.destination_path(destination).exists())
        self.assertEqual(self.editor.changes, {'gold': 100, 'skill_points': 456})

    def test_import_cannot_enable_experimental_mode(self):
        higher = edit_presets.create(replace(self.editor.adapter, experimental=True), self.document,
                                     {'gold': 2000000}, 'Experimental')
        path = self.folder / 'higher.edits.json'
        path.write_bytes(edit_presets.dumps(higher))
        with patch('koei_editor.shared.preset_gui.messagebox.showerror') as errors:
            self.assertFalse(self.dialog.load_path(path))
        errors.assert_called_once()
        self.assertFalse(self.editor.adapter.experimental)
        self.assertFalse(self.editor.experimental_mode.get())
        self.assertEqual((self.editor.changes, self.editor.history), ({}, []))
        self.editor.adapter = replace(self.editor.adapter, experimental=True)
        self.editor.experimental_mode.set(True)
        self.assertTrue(self.dialog.load_path(path))
        self.assertIn('EXPERIMENTAL', self.dialog.summary.get())

    def test_preview_uses_named_choices_for_opened_current_and_final_values(self):
        document = self.document
        mapping = {'gold': ((3456, 'Opened purse'), (5555, 'Current purse'), (12345, 'Plan purse'))}
        with patch.object(self.editor.backend, 'field_options',
                          side_effect=lambda _document, key: mapping.get(key, ()), create=True):
            self.editor.stage_values({'gold': 5555})
            self.load()
        values = self.dialog.tree.item(self.dialog.tree.get_children()[0], 'values')
        self.assertIn('Opened purse', values[1])
        self.assertIn('Current purse', values[2])
        self.assertIn('Plan purse', values[3])
        self.assertIs(self.editor.document, document)

    def test_explicit_opened_assignment_reviews_revert_and_undo_recovers_edit(self):
        revert = replace(self.preset, edits=(edit_presets.PresetEdit('gold', 3456),))
        self.path.write_bytes(edit_presets.dumps(revert))
        self.editor.stage_values({'gold': 12345, 'skill_points': 456})
        previous = dict(self.editor.changes)
        self.load()
        rows = [self.dialog.tree.item(identity, 'values') for identity in self.dialog.tree.get_children()]
        self.assertIn('Revert to opened value', str(rows))
        self.assertTrue(self.dialog.apply_preview())
        self.assertEqual(self.editor.changes, {'skill_points': 456})
        self.editor.undo()
        self.assertEqual(self.editor.changes, previous)

    def test_open_without_a_document_explains_requirement(self):
        self.editor.document = None
        with patch('koei_editor.shared.preset_gui.messagebox.showinfo') as info:
            self.assertIsNone(open_presets(self.editor))
        info.assert_called_once()

    def test_reimport_after_filter_discards_all_detached_rows(self):
        self.editor.stage_values({'skill_points': 456})
        self.load()
        old = tuple(self.dialog._all_identities)
        self.dialog.query.set('gold')
        self.assertEqual(len(self.dialog.tree.get_children()), 1)
        self.load()
        self.assertTrue(all(not self.dialog.tree.exists(identity) for identity in old))
        self.assertEqual(len(self.dialog._all_identities), 2)
        self.assertEqual(len(self.dialog.tree.get_children()), 1)


if __name__ == '__main__':
    unittest.main()
