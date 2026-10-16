"""Management hooks observe completed copy operations without changing editing."""
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.games.origins.origins_game_editor import Editor as ScalarEditor
from koei_editor.games.dw3.gui import Editor as TaggedEditor
from tests.test_origins_parser import fixture
from tests.test_elixirs_v11 import synthetic_reset_save


class WorkspaceEditorHookTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.area = tempfile.TemporaryDirectory()
        self.addCleanup(self.area.cleanup)
        self.folder = Path(self.area.name).resolve()

    def test_snapshot_events_follow_only_successful_fresh_native_operations(self):
        editor = ScalarEditor(self.root)
        source = self.folder / 'SLOT0000.dat'
        raw = fixture(gold=3456)
        source.write_bytes(raw)
        observations = []
        def observe(event):
            self.assertEqual(editor.document.source.read_bytes(), editor.document.raw)
            observations.append((event, editor.document.raw, editor.document.source, dict(editor.changes)))
        editor.on_snapshot = observe
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            self.assertTrue(editor.open_path(source))
            editor.stage_values({'gold': 4567})
            editor.make_backup()
            self.assertEqual(editor.changes, {'gold': 4567})
            self.assertEqual(editor.history, [{}])
            output = self.folder / 'edited.dat'
            editor.save_to(output)
            editor.make_backup()
            errors.assert_not_called()
        self.assertEqual([entry[0] for entry in observations], ['opened', 'backup', 'saved', 'backup'])
        self.assertEqual(observations[0][1], raw)
        self.assertEqual(observations[1][1], raw)
        self.assertEqual(observations[1][3], {'gold': 4567})
        self.assertNotEqual(observations[2][1], raw)
        self.assertEqual(observations[2][2], output)
        self.assertEqual(editor.backup.read_bytes(), observations[-1][1])
        self.assertEqual(source.read_bytes(), raw)
        output.write_bytes(b'changed after opening')
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            editor.make_backup()
        errors.assert_called_once()
        self.assertEqual(len(observations), 4)

    def test_optional_capture_failure_does_not_reject_valid_open_or_save(self):
        editor = ScalarEditor(self.root)
        source = self.folder / 'SLOT0000.dat'
        source.write_bytes(fixture(gold=3456))
        def unavailable(_event):
            raise OSError('Optional local vault unavailable')
        editor.on_snapshot = unavailable
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            self.assertTrue(editor.open_path(source))
            editor.stage_values({'gold': 4567})
            output = self.folder / 'edited.dat'
            editor.save_to(output)
            errors.assert_not_called()
        self.assertTrue(output.exists())
        self.assertIn('Optional snapshot capture did not finish', editor.status.get())
        self.assertEqual(editor.document.source, output)
        self.assertFalse(editor.changes)

    def test_tagged_explicit_open_preserves_backup_and_rolls_back_rejected_input(self):
        editor = TaggedEditor(self.root)
        source = self.folder / 'copy.sav'
        source.write_bytes(synthetic_reset_save().encrypted)
        with patch('koei_editor.games.dw3.gui.messagebox.showerror') as errors:
            self.assertTrue(editor.open_path(source))
            errors.assert_not_called()
        opened, backup = editor.document, editor.backup
        self.assertEqual(backup.read_bytes(), source.read_bytes())
        foreign = self.folder / 'foreign.sav'
        foreign.write_bytes(b'not a tagged save')
        with patch('koei_editor.games.dw3.gui.messagebox.showerror') as errors:
            self.assertFalse(editor.open_path(foreign))
        errors.assert_called_once()
        self.assertIs(editor.document, opened)
        self.assertEqual(editor.backup, backup)
        with patch.object(editor, 'dirty_ok', return_value=False), \
                patch('koei_editor.games.dw3.gui.read_save') as read:
            self.assertFalse(editor.open_path(source))
        read.assert_not_called()
        self.assertIs(editor.document, opened)


if __name__ == '__main__':
    unittest.main()
