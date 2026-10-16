"""Read-only scalar dashboards coexist with the complete editing lifecycle."""
import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.games.origins.origins_game_editor import Editor
from tests.test_origins_parser import fixture


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'),
                     'A graphical display is required.')
class ProgressionWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory()
        self.addCleanup(self.area.cleanup)
        self.folder = Path(self.area.name).resolve()
        self.source = self.folder / 'separate-copy.dat'
        self.original = fixture(gold=3456, skill_points=123)
        self.source.write_bytes(self.original)
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.editor = Editor(self.root)

    def open_copy(self):
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as error:
            self.assertTrue(self.editor.open_path(self.source))
        error.assert_not_called()

    def test_navigation_reveals_hidden_exact_field_without_staging_or_losing_undo(self):
        self.open_copy()
        editor = self.editor
        editor.stage_values({'skill_points': 124})
        pending, history = editor.changes, list(editor.history)
        editor.pending_only.set(True)
        editor.pinned_only.set(True)
        editor.group.set('Resources')
        editor.search.set('no matching field')
        self.assertFalse(editor.fields.exists('gold'))
        self.assertTrue(editor.navigate_dashboard_field('gold'))
        self.assertEqual(editor.workspace_tabs.select(), str(editor.edit_page))
        self.assertEqual(editor.fields.selection(), ('gold',))
        self.assertEqual(editor.fields.focus(), 'gold')
        self.assertEqual(editor.value.get(), '3456')
        self.assertFalse(editor.pending_only.get())
        self.assertFalse(editor.pinned_only.get())
        self.assertEqual(editor.search.get(), '')
        self.assertIs(editor.changes, pending)
        self.assertEqual(editor.changes, {'skill_points': 124})
        self.assertEqual(editor.history, history)
        editor.search.set('retain this filter')
        self.assertFalse(editor.navigate_dashboard_field('unknown-field'))
        self.assertEqual(editor.search.get(), 'retain this filter')
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_opened_projection_is_cached_through_edits_and_replaced_after_saved_copy(self):
        editor = self.editor
        with patch.object(editor.presentation, 'dashboard', wraps=editor.presentation.dashboard) as project:
            self.open_copy()
            self.assertEqual(project.call_count, 1)
            opened = editor.document
            editor.search.set('gold')
            editor.stage_values({'gold': 4567})
            editor.undo()
            editor.stage_values({'gold': 4567})
            self.assertEqual(project.call_count, 1)
            self.assertIs(editor.document, opened)
            self.assertEqual(editor.adapter.field_map(opened)['gold'].value(opened.payload), 3456)
            output = self.folder / 'edited-copy.dat'
            editor.save_to(output)
            self.assertEqual(project.call_count, 2)
            self.assertIsNot(editor.document, opened)
            self.assertIs(project.call_args.args[0], editor.document)
            self.assertEqual(editor.adapter.field_map(editor.document)['gold'].value(editor.document.payload), 4567)
        self.assertFalse(editor.changes)
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual(editor.backup.read_bytes(), self.original)

    def test_rejected_open_preserves_the_previous_projection_and_pending_values(self):
        self.open_copy()
        editor = self.editor
        editor.stage_values({'gold': 4567})
        document, pending, history = editor.document, editor.changes, list(editor.history)
        foreign = self.folder / 'foreign-copy.dat'
        foreign.write_bytes(b'not a supported save')
        with patch.object(editor.dashboard_view, 'set_dashboard') as render, \
                patch('koei_editor.shared.verified_gui.messagebox.showerror') as error:
            self.assertFalse(editor.open_path(foreign))
        error.assert_called_once()
        render.assert_not_called()
        self.assertIs(editor.document, document)
        self.assertIs(editor.changes, pending)
        self.assertEqual(editor.history, history)
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_projection_failure_keeps_validated_editing_and_backups_available(self):
        editor = self.editor
        with patch.object(editor.presentation, 'dashboard', side_effect=ValueError('Display mapping unavailable')), \
                patch.object(editor.dashboard_view, 'set_dashboard') as render:
            self.open_copy()
        self.assertIn('could not be displayed', render.call_args.args[0].note)
        self.assertTrue(editor.navigate_dashboard_field('gold'))
        editor.stage_values({'gold': 4567})
        self.assertEqual(editor.changes, {'gold': 4567})
        self.assertEqual(editor.backup.read_bytes(), self.original)
        self.assertEqual(self.source.read_bytes(), self.original)


if __name__ == '__main__':
    unittest.main()
