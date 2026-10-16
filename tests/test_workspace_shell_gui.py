"""Retained utility navigation, guarded handoffs and cancellable-close semantics."""
from pathlib import Path
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import ttk
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

from koei_editor.application import Application
from koei_editor.shared.appearance import THEMES
from tests.test_origins_parser import fixture


class Utility:
    """A real Tk contract fixture; feature parser behavior is tested separately."""
    def __init__(self, root, parent, on_open=None, session_provider=None, vault_root=None, auto_capture=None):
        self.frame = ttk.Frame(parent)
        self.search = ttk.Entry(self.frame)
        self.search.pack(fill='x')
        self.on_open, self.session_provider, self.vault_root = on_open, session_provider, vault_root
        self.busy, self.pending = False, False
        self.cancelled = threading.Event()
        self.closed = 0
        self.palettes = []

    def apply_theme(self, palette):
        self.palettes.append(palette)

    def focus_search(self):
        self.search.focus_set()
        return 'break'

    def close(self):
        self.closed += 1
        self.cancelled.set()

    def has_pending_work(self):
        return self.pending


class WorkspaceShellGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.root.destroy)
        self.area = tempfile.TemporaryDirectory()
        self.addCleanup(self.area.cleanup)
        self.folder = Path(self.area.name).resolve()
        modules = {}
        for suffix, class_name in (
            ('save_doctor_gui', 'SaveDoctorWorkspace'),
            ('compatible_preset_gui', 'CompatiblePresetWorkspace'),
            ('save_detection_gui', 'SaveDetectionWorkspace'),
            ('save_vault_gui', 'SaveVaultWorkspace'),
        ):
            name = 'koei_editor.shared.' + suffix
            module = ModuleType(name)
            setattr(module, class_name, Utility)
            modules[name] = module
        self.patcher = patch.dict(sys.modules, modules)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.app = Application(self.root, preferences_path=self.folder / 'prefs.json',
                               persist_preferences=False, vault_root=self.folder / 'private-vault')
        self.root.geometry('1080x820')
        self.root.update()

    def test_compact_header_and_complete_palette_fit_themes_and_long_breadcrumbs(self):
        app = self.app
        app.breadcrumb.set('A long exact game/platform revision ' * 100)
        self.root.minsize(650, 500)
        for width, height in ((1080, 820), (800, 650)):
            self.root.geometry(f'{width}x{height}')
            for theme in THEMES:
                app.apply_theme(theme)
                self.root.update()
                for control in (app.home_button, app.tools_button, app.author_label, app.theme_selector):
                    self.assertTrue(control.winfo_ismapped())
                    self.assertGreater(control.winfo_width(), 10)
                    self.assertLessEqual(control.winfo_rootx() + control.winfo_width(), self.root.winfo_rootx() + width)
                self.assertGreater(app.breadcrumb_label.winfo_width(), 1)
                self.root.focus_force()
                app.tools_button.invoke()
                self.root.update()
                self.assertTrue(app.tools_menu.visible)
                for button in app.tools_menu.buttons.values():
                    self.assertTrue(button.winfo_ismapped())
                self.assertEqual(app.tools_menu.window['background'], THEMES[theme]['border'])
                self.assertLess(app.tools_menu.window.winfo_height(), height)
                app.tools_menu.window.event_generate('<Escape>')
                self.root.update()
                self.assertFalse(app.tools_menu.visible)

    def test_all_four_workspaces_are_lazy_retained_themed_and_search_local(self):
        app = self.app
        self.assertEqual(app._tool_workspaces(), ())
        self.assertFalse((self.folder / 'private-vault').exists())
        before = app.platform_choice.get(), app.library_search.get()
        retained = {}
        for method, attribute in (
            ('show_save_doctor', 'save_doctor'), ('show_save_detection', 'save_detection'),
            ('show_compatible_presets', 'compatible_presets'), ('show_save_vault', 'save_vault'),
        ):
            tool = getattr(app, method)()
            retained[attribute] = tool
            tool.search.insert(0, attribute)
            self.assertEqual(app.active_tool, attribute)
            self.assertEqual(tool.frame.winfo_manager(), 'pack')
            self.assertIsNone(app.active_game)
            self.assertEqual(app.focus_library_search(), 'break')
            self.assertEqual(before, (app.platform_choice.get(), app.library_search.get()))
            app.show_library()
            self.assertFalse(tool.frame.winfo_manager())
            self.assertIs(getattr(app, method)(), tool)
            self.assertEqual(tool.search.get(), attribute)
        self.assertEqual(len(app._tool_workspaces()), 4)
        app.apply_theme('Dark')
        for tool in retained.values():
            self.assertEqual(tool.palettes[-1], THEMES['Dark'])
        self.assertEqual(app.save_vault.vault_root, self.folder / 'private-vault')
        self.assertFalse((self.folder / 'private-vault').exists())

    def test_utility_open_rejection_preserves_pending_history_and_current_workspace(self):
        source = self.folder / 'separate-copy.dat'
        original = fixture()
        source.write_bytes(original)
        app = self.app
        editor = app.select_game('origins')
        self.assertTrue(editor.open_path(source))
        editor.stage_values({'gold': 4567})
        document, changes, history = editor.document, editor.changes, list(editor.history)
        doctor = app.show_save_doctor()
        foreign = self.folder / 'foreign.dat'
        foreign.write_bytes(b'foreign data')
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as error:
            self.assertFalse(doctor.on_open('origins', foreign))
        error.assert_called_once()
        self.assertIs(editor.document, document)
        self.assertIs(editor.changes, changes)
        self.assertEqual(editor.history, history)
        self.assertEqual(app.active_tool, 'save_doctor')
        self.assertTrue(doctor.frame.winfo_manager())
        with patch.object(editor, 'dirty_ok', return_value=False):
            self.assertFalse(doctor.on_open('origins', source))
        self.assertEqual(editor.changes, {'gold': 4567})
        self.assertEqual(source.read_bytes(), original)
        with patch.object(editor, 'dirty_ok', return_value=True):
            self.assertTrue(doctor.on_open('origins', source))
        self.assertEqual(app.active_game, 'origins')
        self.assertFalse(doctor.frame.winfo_manager())
        self.assertFalse(editor.changes)

    def test_preset_provider_tracks_real_retained_sessions_without_creating_new_ones(self):
        app = self.app
        first = app.select_game('origins')
        second = app.select_game('dw6')
        presets = app.show_compatible_presets()
        self.assertEqual([editor for _, editor in presets.session_provider()], [second, first])
        self.assertEqual(set(app.sessions), {'origins', 'dw6'})
        app.select_game('origins')
        self.assertEqual([editor for _, editor in app.preset_sessions()], [first, second])
        self.assertIs(app.show_compatible_presets(), presets)

    def test_close_blocks_writes_but_cancels_reads_only_after_editors_accept(self):
        app = self.app
        doctor = app.show_save_doctor()
        doctor.busy = True
        doctor.pending = True
        with patch('tkinter.messagebox.showinfo') as info, patch.object(self.root, 'destroy') as destroy:
            app.close()
            info.assert_called_once()
            destroy.assert_not_called()
        self.assertEqual(doctor.closed, 0)
        doctor.pending = False
        editor = app.select_game('origins')
        worker = threading.Thread(target=doctor.cancelled.wait, args=(2,))
        worker.start()
        with patch.object(editor, 'dirty_ok', return_value=False), patch.object(self.root, 'destroy') as destroy:
            app.close()
            destroy.assert_not_called()
        self.assertFalse(doctor.cancelled.is_set())
        with patch.object(editor, 'dirty_ok', return_value=True), patch.object(self.root, 'destroy') as destroy:
            app.close()
            destroy.assert_called_once()
        worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(doctor.closed, 1)

    def test_optional_vault_capture_is_explicit_and_failures_do_not_change_editor(self):
        app = self.app
        editor = app.select_game('origins')
        module = ModuleType('koei_editor.shared.save_vault')
        capture = module.capture_editor_backup = Mock(return_value='snapshot-id')
        with patch.dict(sys.modules, {module.__name__: module}):
            self.assertFalse(app.capture_editor_backup('origins', editor))
            capture.assert_not_called()
            app.vault_auto_capture.set(True)
            self.assertEqual(app.capture_editor_backup('origins', editor), 'snapshot-id')
            capture.assert_called_once_with('origins', editor, root=self.folder / 'private-vault', event='opened')
            capture.side_effect = OSError('A private local path is deliberately not displayed')
            self.assertFalse(app.capture_editor_backup('origins', editor))
        self.assertIn('Vault capture failed', app.vault_capture_status.get())
        self.assertNotIn('private local path', app.vault_capture_status.get())
        self.assertIsNone(editor.document)
        self.assertFalse(editor.changes)
        self.assertFalse((self.folder / 'private-vault').exists())

    def test_palette_outside_click_keyboard_focus_and_existing_action_buttons(self):
        app = self.app
        self.root.focus_force()
        self.root.update()
        app.tools_button.invoke()
        self.root.update()
        self.assertIs(self.root.focus_get(), app.save_library_button)
        app.save_library_button.event_generate('<Down>')
        self.root.update()
        self.assertIs(self.root.focus_get(), app.save_doctor_button)
        app.breadcrumb_label.event_generate('<Button-1>', x=1, y=1)
        self.root.update()
        self.assertFalse(app.tools_menu.visible)
        app.tools_button.invoke()
        self.root.update()
        app.save_doctor_button.invoke()
        self.root.update()
        self.assertFalse(app.tools_menu.visible)
        self.assertEqual(app.active_tool, 'save_doctor')
        self.assertTrue(app.save_doctor.frame.winfo_manager())
        self.assertFalse(any(isinstance(child, tk.Toplevel) for child in self.root.winfo_children()))

    def test_workspace_close_can_refuse_final_teardown(self):
        tool = self.app.show_save_doctor()
        with patch.object(tool, 'close', return_value=False) as close, patch.object(self.root, 'destroy') as destroy:
            self.app.close()
            close.assert_called_once()
            destroy.assert_not_called()

    def test_registered_bespoke_editor_uses_its_guarded_path_open_capability(self):
        editor = Mock(spec=['open_path'])
        editor.open_path.return_value = True
        path = self.folder / 'explicit-dw3-copy.dat'
        with patch.object(self.app, '_session_editor', return_value=editor), \
                patch.object(self.app, 'select_game') as select:
            self.assertTrue(self.app.open_saved_copy('dw3', path))
        editor.open_path.assert_called_once_with(path)
        select.assert_called_once_with('dw3')


if __name__ == '__main__':
    unittest.main()
