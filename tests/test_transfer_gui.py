"""Live selective transfer previews, atomic staging, rollback and one-step Undo."""
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.game_registry import get_game
from koei_editor.shared.transfer_gui import open_transfer
from tests.test_origins_parser import fixture


class TransferGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.root.destroy)
        self.root.withdraw()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder / 'source.dat'
        self.target = self.folder / 'target.dat'
        self.source.write_bytes(fixture(gold=1234, skill_points=44))
        self.target.write_bytes(fixture())
        self.editor = get_game('origins').create_editor(self.root, self.root)
        with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(self.target)):
            self.editor.open()
        self.dialog = open_transfer(self.editor)
        self.root.update()

    def load(self):
        with patch('koei_editor.shared.transfer_gui.messagebox.showerror') as errors:
            self.assertTrue(self.dialog.load_source(self.source))
        errors.assert_not_called()
        self.root.update()

    def preview(self, keys=('gold',)):
        self.dialog.choices.selection_set(keys)
        self.root.update()
        with patch('koei_editor.shared.transfer_gui.messagebox.showerror') as errors:
            self.assertTrue(self.dialog.prepare_preview())
        errors.assert_not_called()

    def test_select_preview_apply_is_one_undo_and_both_files_remain_unchanged(self):
        self.editor.stage_values({'skill_points': 90})
        original, history = dict(self.editor.changes), list(self.editor.history)
        self.load()
        self.preview()
        self.assertEqual(len(self.dialog.preview.get_children()), 2)
        self.assertEqual(self.editor.changes, original)
        self.assertTrue(self.dialog.apply_preview())
        self.assertEqual(self.editor.changes, {'skill_points': 90, 'gold': 1234})
        self.assertEqual(self.editor.history, history + [original])
        self.editor.undo()
        self.assertEqual((self.editor.changes, self.editor.history), (original, history))
        self.assertEqual(self.source.read_bytes(), fixture(gold=1234, skill_points=44))
        self.assertEqual(self.target.read_bytes(), fixture())

    def test_filter_keeps_hidden_selection_and_preview_includes_it(self):
        self.load()
        self.dialog.choices.selection_set(('gold', 'skill_points'))
        self.root.update()
        self.dialog.query.set('gold')
        self.root.update()
        self.assertEqual(len(self.dialog.choices.get_children()), 1)
        self.assertEqual(self.dialog.selected, {'gold', 'skill_points'})
        self.assertTrue(self.dialog.prepare_preview())
        self.assertEqual(set(self.dialog.plan.selected), {'gold', 'skill_points'})

    def test_selection_change_invalidates_preview(self):
        self.load()
        self.preview()
        self.dialog.choices.selection_set(('skill_points',))
        self.root.update()
        self.assertIsNone(self.dialog.plan)
        self.assertEqual(str(self.dialog.apply_button['state']), 'disabled')
        self.assertEqual(self.editor.changes, {})

    def test_source_change_or_pending_change_rejects_apply_without_history_mutation(self):
        self.load()
        self.preview()
        self.editor.stage_values({'skill_points': 90})
        original = (dict(self.editor.changes), list(self.editor.history))
        with patch('koei_editor.shared.transfer_gui.messagebox.showerror') as errors:
            self.assertFalse(self.dialog.apply_preview())
        self.assertIn('Pending edits changed', str(errors.call_args))
        self.assertEqual((self.editor.changes, self.editor.history), original)
        self.preview()
        self.source.write_bytes(fixture(gold=12))
        with patch('koei_editor.shared.transfer_gui.messagebox.showerror'):
            self.assertFalse(self.dialog.apply_preview())
        self.assertEqual((self.editor.changes, self.editor.history), original)

    def test_refresh_failure_and_source_change_during_commit_roll_back_everything(self):
        self.load()
        self.preview()
        with patch.object(self.editor, 'refresh', side_effect=RuntimeError('Display failed')), \
                patch('koei_editor.shared.transfer_gui.messagebox.showerror'):
            self.assertFalse(self.dialog.apply_preview())
        self.assertEqual((self.editor.changes, self.editor.history), ({}, []))
        self.preview()
        accept = self.editor._accept_pending
        def change_source(result):
            accept(result)
            self.source.write_bytes(fixture(gold=12))
        with patch.object(self.editor, '_accept_pending', side_effect=change_source), \
                patch('koei_editor.shared.transfer_gui.messagebox.showerror'):
            self.assertFalse(self.dialog.apply_preview())
        self.assertEqual((self.editor.changes, self.editor.history), ({}, []))
        self.assertNotIn('1,234', str(self.editor.fields.item('gold', 'values')))

    def test_cancel_source_keeps_preview_bad_source_clears_it_and_destination_session_rejected(self):
        self.load()
        self.preview()
        plan = self.dialog.plan
        with patch('koei_editor.shared.transfer_gui.filedialog.askopenfilename', return_value=''):
            self.assertFalse(self.dialog.choose_source())
        self.assertIs(self.dialog.plan, plan)
        with patch('koei_editor.shared.transfer_gui.messagebox.showerror'):
            self.assertFalse(self.dialog.load_source(self.target))
        self.assertIsNone(self.dialog.plan)
        self.assertFalse(self.dialog.choices.get_children())
        self.load()
        self.preview()
        self.editor.document = None
        with patch('koei_editor.shared.transfer_gui.messagebox.showerror'):
            self.assertFalse(self.dialog.apply_preview())
        self.assertEqual((self.editor.changes, self.editor.history), ({}, []))

    def test_no_document_explains_destination_requirement(self):
        self.editor.document = None
        with patch('koei_editor.shared.transfer_gui.messagebox.showinfo') as info:
            self.assertIsNone(open_transfer(self.editor))
        info.assert_called_once()


if __name__ == '__main__':
    unittest.main()
