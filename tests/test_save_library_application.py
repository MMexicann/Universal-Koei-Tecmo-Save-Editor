"""Application wiring for copied-save browsing and exact-profile field pins."""
import json
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.application import Application
from koei_editor.game_registry import get_game
from koei_editor.shared import preferences, save_library
from tests.test_origins_parser import fixture


class SaveLibraryApplicationTests(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory()
        self.addCleanup(self.area.cleanup)
        self.folder = Path(self.area.name)
        self.prefs = self.folder / 'preferences.json'
        self.copies = self.folder / 'copies'
        self.copies.mkdir()
        self.source = self.copies / 'SLOT0000.dat'
        self.second = self.copies / 'SLOT0001.dat'
        self.raw = fixture()
        self.source.write_bytes(self.raw)
        self.second.write_bytes(self.raw)
        self.root = self.new_root()
        self.app = Application(self.root, preferences_path=self.prefs)
        self.root.geometry('1080x820')
        self.root.update()

    def new_root(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        def destroy():
            try:
                root.destroy()
            except tk.TclError:
                pass
        self.addCleanup(destroy)
        return root

    def browser(self):
        self.app.show_save_library()
        gui = self.app.save_library
        gui.game.set(next(label for label, game_id in gui._games.items() if game_id == 'origins'))
        gui.folder.set(str(self.copies))
        self.root.update()
        return gui

    def finish(self, gui):
        deadline = time.monotonic() + 20
        while gui.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertFalse(gui.busy, 'Save Library worker did not finish.')
        self.root.update()

    @staticmethod
    def select(gui, name):
        index = next(index for index, entry in enumerate(gui.prepared.entries)
                     if entry.relative_path == name)
        gui.table.selection_set(str(index))
        gui.selection_changed()

    def test_scan_open_normal_backup_theme_navigation_and_retained_workspace(self):
        self.assertIsNone(self.app.save_library)
        self.app.save_library_button.invoke()
        gui = self.browser()
        gui.scan()
        self.finish(gui)
        result = gui.prepared
        self.assertEqual(result.qualified_count, 2)
        self.assertFalse(self.prefs.exists(), 'Startup and scanning must not rewrite preferences.')
        self.app.show_converter()
        self.app.show_save_library()
        self.assertIs(self.app.save_library, gui)
        self.assertIs(gui.prepared, result)
        self.app.apply_theme('Dark')
        self.assertEqual(self.app.theme_name.get(), 'Dark')
        self.assertIn(gui, self.app._tool_workspaces())
        self.assertEqual(self.app.breadcrumb.get(), 'Save Library')
        self.root.focus_force()
        self.app.focus_library_search()
        self.root.update()
        self.assertIs(self.root.focus_get(), gui.search_entry)
        self.assertTrue(gui.frame.winfo_ismapped())
        self.select(gui, self.source.name)
        with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename',
                   side_effect=AssertionError('Browser opening must not ask for a second path')):
            gui.open_selected()
            self.finish(gui)
        self.assertEqual(self.app.active_game, 'origins')
        editor = self.app.sessions['origins'][1]
        self.assertTrue(editor.document.source.samefile(self.source))
        self.assertEqual(editor.document.raw, self.raw)
        self.assertEqual(editor.backup.read_bytes(), self.raw)
        self.assertEqual(editor.theme_name.get(), 'Dark')
        self.assertFalse(gui.frame.winfo_ismapped())
        editor.stage_values({'gold': 1234})
        self.app.show_save_library()
        self.assertIs(gui.prepared, result)
        self.app.show_library()
        self.assertIs(self.app.select_game('origins'), editor)
        self.assertEqual(editor.changes, {'gold': 1234})
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertEqual(self.second.read_bytes(), self.raw)

    def test_dirty_decline_keeps_browser_visible_and_existing_session_unchanged(self):
        editor = self.app.select_game('origins')
        self.assertTrue(editor.open_path(self.source))
        editor.stage_values({'gold': 111})
        document, backup, history = editor.document, editor.backup, list(editor.history)
        gui = self.browser()
        gui.scan()
        self.finish(gui)
        self.select(gui, self.second.name)
        before = {p: p.read_bytes() for p in self.folder.rglob('*') if p.is_file()}
        with patch('koei_editor.shared.verified_gui.messagebox.askyesno', return_value=False) as prompt:
            gui.open_selected()
            self.finish(gui)
        prompt.assert_called_once()
        self.assertIs(editor.document, document)
        self.assertEqual(editor.backup, backup)
        self.assertEqual(editor.changes, {'gold': 111})
        self.assertEqual(editor.history, history)
        self.assertIsNone(self.app.active_game)
        self.assertTrue(gui.frame.winfo_ismapped())
        self.assertEqual({p: p.read_bytes() for p in self.folder.rglob('*') if p.is_file()}, before)
        with patch('koei_editor.shared.verified_gui.messagebox.askyesno', return_value=True):
            self.assertTrue(self.app.open_saved_copy('origins', self.second))
        self.assertEqual(self.app.active_game, 'origins')
        self.assertTrue(editor.document.source.samefile(self.second))
        self.assertEqual((editor.changes, editor.history), ({}, []))

    def test_copy_changed_between_browser_recheck_and_editor_open_is_rejected(self):
        gui = self.browser()
        gui.scan()
        self.finish(gui)
        self.select(gui, self.source.name)
        original = save_library.requalify
        def change_after_recheck(*args, **kwargs):
            document = original(*args, **kwargs)
            self.source.write_bytes(self.raw[:-1])
            return document
        with patch.object(save_library, 'requalify', side_effect=change_after_recheck), \
             patch('koei_editor.shared.verified_gui.messagebox.showerror') as error:
            gui.open_selected()
            self.finish(gui)
        error.assert_called_once()
        self.assertIsNone(self.app.sessions['origins'][1].document)
        self.assertIsNone(self.app.active_game)
        self.assertTrue(gui.frame.winfo_ismapped())
        self.assertFalse(any('backup' in p.name.casefold() for p in self.copies.iterdir()))
        self.assertEqual(self.source.read_bytes(), self.raw[:-1])
        self.assertEqual(self.second.read_bytes(), self.raw)

    def test_busy_close_waits_then_dirty_decline_preserves_workspace_then_closes_polling(self):
        gui = self.browser()
        gui.busy = True
        with patch('tkinter.messagebox.showinfo') as notice, patch.object(self.root, 'destroy') as destroy:
            self.app.close()
        notice.assert_called_once()
        destroy.assert_not_called()
        self.assertFalse(gui._closed)
        gui.busy = False
        editor = self.app._session_editor(get_game('origins'))
        editor.open_path(self.source)
        editor.stage_values({'gold': 17})
        with patch('koei_editor.shared.verified_gui.messagebox.askyesno', return_value=False), \
             patch.object(self.root, 'destroy') as destroy:
            self.app.close()
        destroy.assert_not_called()
        self.assertFalse(gui._closed)
        with patch('koei_editor.shared.verified_gui.messagebox.askyesno', return_value=True), \
             patch.object(self.root, 'destroy') as destroy:
            self.app.close()
        destroy.assert_called_once()
        self.assertTrue(gui._closed)
        self.assertTrue(gui._cancel.is_set())
        self.assertIsNone(gui._poll_id)

    def test_pins_persist_per_profile_and_theme_across_actual_application_restart(self):
        editor = self.app.select_game('origins')
        editor.open_path(self.source)
        editor.fields.selection_set('gold')
        editor.pin_selected()
        self.app.apply_theme('Dark')
        self.assertEqual(preferences.load_pins('origins', self.prefs), ('gold',))
        self.assertEqual(preferences.load_theme(self.prefs), 'Dark')
        self.assertEqual(self.app.select_game('dw7xl').pinned_fields, frozenset())
        self.assertFalse(self.app.sessions['origins'][1].changes)
        self.app.close()
        reopened_root = self.new_root()
        reopened = Application(reopened_root, preferences_path=self.prefs)
        reopened_editor = reopened.select_game('origins')
        self.assertEqual(reopened_editor.theme_name.get(), 'Dark')
        self.assertEqual(reopened_editor.pinned_fields, frozenset(('gold',)))
        self.assertIsNone(reopened_editor.document)
        self.assertFalse(reopened_editor.changes)
        self.assertEqual(set(json.loads(self.prefs.read_bytes())), {'schema', 'theme', 'pins'})

    def test_disabled_persistence_reads_existing_pins_but_never_writes_pin_or_theme_changes(self):
        self.app.close()
        preferences.save_theme('Dark', self.prefs)
        preferences.save_pins('origins', ['skill_points'], self.prefs)
        before = self.prefs.read_bytes()
        root = self.new_root()
        app = Application(root, preferences_path=self.prefs, persist_preferences=False)
        editor = app.select_game('origins')
        self.assertEqual(editor.pinned_fields, frozenset(('skill_points',)))
        editor.open_path(self.source)
        editor.fields.selection_set('gold')
        with patch.object(preferences, 'save_pins') as pins, patch.object(preferences, 'save_theme') as theme:
            editor.pin_selected()
            app.apply_theme('Light')
            app.show_save_library()
            app.show_library()
            app.select_game('origins')
            pins.assert_not_called()
            theme.assert_not_called()
        self.assertEqual(editor.pinned_fields, frozenset(('gold', 'skill_points')))
        self.assertEqual(self.prefs.read_bytes(), before)
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_unsupported_browser_profile_rejected_before_creating_session(self):
        self.app.show_save_library()
        self.root.update()
        with patch('tkinter.messagebox.showerror') as error:
            self.assertFalse(self.app.open_saved_copy('dw3', self.source))
        error.assert_called_once()
        self.assertNotIn('dw3', self.app.sessions)
        self.assertTrue(self.app.save_library.frame.winfo_ismapped())


if __name__ == '__main__':
    unittest.main()
