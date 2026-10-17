"""Application entries reach retained editing tools through existing save sessions."""
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.application import Application, VERSION
from tests.test_origins_parser import fixture


class EditingToolsApplicationTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.root.destroy)
        area = tempfile.TemporaryDirectory()
        self.addCleanup(area.cleanup)
        self.folder = Path(area.name)
        self.app = Application(self.root, persist_preferences=False,
                               preferences_path=self.folder / 'preferences.json')
        self.root.geometry('1080x820')

    def open_destination(self):
        editor = self.app.select_game('origins')
        path = self.folder / 'SLOT0000.dat'
        path.write_bytes(fixture())
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            self.assertTrue(editor.open_path(path))
            errors.assert_not_called()
        return editor

    def test_menu_reaches_retained_research_and_presets_and_preserves_editor(self):
        editor = self.open_destination()
        editor.stage_values({'gold': 12345})
        before = (dict(editor.changes), list(editor.history))
        self.app.editing_tools_menu.invoke(0)
        presets = self.app.editing_presets
        self.root.update()
        self.assertTrue(presets.frame.winfo_ismapped())
        self.assertIn(editor, presets._sessions.values())
        self.app.editing_tools_menu.invoke(3)
        research = self.app.research_lab
        self.root.update()
        self.assertTrue(research.frame.winfo_ismapped())
        self.assertFalse(presets.frame.winfo_ismapped())
        with patch.object(research, 'apply_theme', wraps=research.apply_theme) as research_theme, \
                patch.object(presets, 'apply_theme', wraps=presets.apply_theme) as preset_theme:
            for theme in ('Dark', 'Light'):
                self.app.apply_theme(theme)
            self.assertEqual(research_theme.call_count, 2)
            self.assertEqual(preset_theme.call_count, 2)
        self.app.show_library()
        self.app.show_research_lab()
        self.assertIs(self.app.research_lab, research)
        self.app.show_editing_presets()
        self.assertIs(self.app.editing_presets, presets)
        self.assertIs(self.app.select_game('origins'), editor)
        self.assertEqual((editor.changes, editor.history), before)
        self.assertEqual(editor.document.source.read_bytes(), editor.document.raw)
        self.assertEqual(VERSION, '2.7')

    def test_transfer_requires_open_destination_then_uses_that_exact_editor(self):
        with patch('tkinter.messagebox.showinfo') as info:
            self.assertIsNone(self.app.show_transfer())
            info.assert_called_once()
        editor = self.open_destination()
        dialog = self.app.show_transfer()
        self.assertIs(dialog.editor, editor)
        self.assertEqual((editor.changes, editor.history), ({}, []))
        dialog.close()

    def test_root_close_respects_busy_research_and_target_editor_dirty_guard(self):
        research = self.app.show_research_lab()
        research.busy = True
        with patch('tkinter.messagebox.showinfo') as info, patch.object(self.root, 'destroy') as destroy:
            self.app.close()
            info.assert_called_once()
            destroy.assert_not_called()
        research.busy = False
        presets = self.app.show_editing_presets()
        with patch.object(presets, 'dirty_ok', return_value=False) as guard, \
                patch.object(self.root, 'destroy') as destroy:
            self.app.close()
            guard.assert_called_once()
            destroy.assert_not_called()
        with patch.object(presets, 'dirty_ok', return_value=True), \
                patch.object(presets, 'close') as close, patch.object(self.root, 'destroy') as destroy:
            self.app.close()
            close.assert_called_once()
            destroy.assert_called_once()


if __name__ == '__main__':
    unittest.main()
