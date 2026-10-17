"""Bulk failure feedback and exact navigation preserve the complete edit session."""
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.game_registry import get_game
from tests.test_origins_parser import fixture


class ScalarEditSafetyTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.root.destroy)
        self.root.withdraw()
        area = tempfile.TemporaryDirectory()
        self.addCleanup(area.cleanup)
        self.source = Path(area.name) / 'SLOT0000.dat'
        self.source.write_bytes(fixture())
        self.editor = get_game('origins').create_editor(self.root, self.root)
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            self.assertTrue(self.editor.open_path(self.source))
            errors.assert_not_called()

    def test_all_invalid_assignments_are_named_and_entire_batch_is_retained(self):
        editor = self.editor
        editor.stage_values({'dlc_skill_points': 77})
        before = (dict(editor.changes), list(editor.history))
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            self.assertFalse(editor.stage_values({'gold': -1, 'skill_points': -2}))
        errors.assert_called_once()
        detail = errors.call_args.args[1]
        self.assertIn('2 selected values failed', detail)
        self.assertIn('[gold]', detail)
        self.assertIn('[skill_points]', detail)
        self.assertIn('not staged', editor.status.get())
        self.assertEqual((editor.changes, editor.history), before)
        self.assertEqual(self.source.read_bytes(), editor.document.raw)

    def test_refresh_failure_rolls_back_regular_edit_and_undo_history(self):
        editor = self.editor
        editor.stage_values({'gold': 100})
        before = (dict(editor.changes), list(editor.history))
        with patch.object(editor, 'refresh', side_effect=RuntimeError('View unavailable')), \
                patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            self.assertFalse(editor.stage_values({'skill_points': 200}))
        errors.assert_called_once()
        self.assertEqual((editor.changes, editor.history), before)
        self.assertEqual(self.source.read_bytes(), editor.document.raw)

    def test_backend_side_effect_cannot_silently_replace_a_selected_assignment(self):
        editor = self.editor
        stage = editor.backend.stage
        def side_effect(document, changes, key, value):
            result = stage(document, changes, key, value)
            if key == 'skill_points':
                result['gold'] = 99
            return result
        with patch.object(editor.backend, 'stage', side_effect=side_effect), \
                patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            self.assertFalse(editor.stage_values({'gold': 100, 'skill_points': 200}))
        self.assertIn('changed by another selected assignment', errors.call_args.args[1])
        self.assertEqual((editor.changes, editor.history), ({}, []))

    def test_enter_exact_field_reveals_it_across_conflicting_filters(self):
        editor = self.editor
        editor.stage_values({'gold': 100})
        before = (dict(editor.changes), list(editor.history))
        editor.group.set('Bonds')
        editor.pending_only.set(True)
        editor.pinned_only.set(True)
        editor.search.set('skill_points')
        self.assertFalse(editor.fields.exists('skill_points'))
        self.assertEqual(editor.select_field_match(), 'break')
        self.assertEqual(editor.fields.selection(), ('skill_points',))
        self.assertEqual(editor.fields.focus(), 'skill_points')
        self.assertEqual((editor.changes, editor.history), before)

    def test_next_pending_reveals_hidden_fields_and_wraps_without_editing(self):
        editor = self.editor
        editor.stage_values({'gold': 100, 'skill_points': 200})
        before = (dict(editor.changes), list(editor.history))
        editor.search.set('gold')
        editor.fields.focus('gold')
        editor.next_pending_field()
        self.assertEqual(editor.fields.selection(), ('skill_points',))
        editor.next_pending_field()
        self.assertEqual(editor.fields.selection(), ('gold',))
        self.assertEqual((editor.changes, editor.history), before)
        self.assertEqual(self.source.read_bytes(), editor.document.raw)


if __name__ == '__main__':
    unittest.main()
