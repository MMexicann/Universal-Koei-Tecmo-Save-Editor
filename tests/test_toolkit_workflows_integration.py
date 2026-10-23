"""Real desktop routing, dirty-session retention, and local companion lifecycle."""

import http.client
import json
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import font as tkfont
from urllib.parse import urlsplit
import unittest
from unittest.mock import patch

from koei_editor.application import Application
from koei_editor.shared import mod_manager, verified_editor
from koei_editor.shared.localization import LANGUAGES
from koei_editor.shared.mod_workshop.manager_export import export_manager_package, review_manager_package
from koei_editor.shared.save_discovery import DiscoveryResult
from tests.test_mod_workshop_manager import make_workshop
from tests.test_verified_editors import synthetic_raw


class ToolkitWorkflowIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name).resolve()
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self._close)
        preference_patch = patch('koei_editor.shared.mod_manager_gui.preference_path',
                                 return_value=self.folder / 'preferences.json')
        preference_patch.start()
        self.addCleanup(preference_patch.stop)
        self.app = Application(self.root, preferences_path=self.folder / 'preferences.json',
                               persist_preferences=False)
        self.callback_errors = []
        self.root.report_callback_exception = lambda *error: self.callback_errors.append(error)
        self.root.geometry('780x680')
        self.root.update()

    def _close(self):
        if hasattr(self, 'app'):
            for tool in self.app._tool_workspaces():
                close = getattr(tool, 'close', None)
                if callable(close):
                    close()
            if self.app.browser_companions is not None:
                self.app.browser_companions.close()
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def dirty_editor(self):
        editor = self.app.select_game('dw8xl')
        raw = synthetic_raw('dw8xl')
        editor.document = verified_editor.decode(raw, 'dw8xl')
        editor.refresh()
        editor.stage_values({'gold': 123})
        self.assertEqual(editor.changes, {'gold': 123})
        return editor

    def test_every_tools_action_routes_and_retains_real_pending_edit(self):
        editor = self.dirty_editor()
        opened = editor.document
        directory = self.app.show_tool_directory()
        empty = DiscoveryResult((), (), (), 'complete', 0, 0, ())
        with patch('koei_editor.shared.game_hub.discover_installations', return_value=empty), \
                patch('koei_editor.shared.browser_companions.webbrowser.open', return_value=True), \
                patch('koei_editor.mods.nexus_browser.NexusApiClient') as api, \
                patch('tkinter.messagebox.showerror') as errors:
            for entry in directory.entries:
                with self.subTest(tool=entry.command_id):
                    # Transfer needs the active destination; all actions use the
                    # same command dispatcher as the Tools row callback.
                    self.app.select_game('dw8xl')
                    result = self.app.execute_command(entry.command_id)
                    self.root.update()
                    self.assertIs(self.app.sessions['dw8xl'][1], editor)
                    self.assertIs(editor.document, opened)
                    self.assertEqual(editor.changes, {'gold': 123})
                    if entry.command_id == 'tool:transfer' and result is not None:
                        result.close()
            api.assert_not_called()
            errors.assert_not_called()
        self.assertFalse(self.callback_errors)
        self.assertIsNotNone(self.app.browser_companions)

    def test_nioh3_manual_nexus_zip_routes_to_its_library_without_install(self):
        package = self.folder / 'nioh3.zip'
        import zipfile
        with zipfile.ZipFile(package, 'w') as archive:
            archive.writestr('koei-mod.json', json.dumps({
                'schema_version': 1, 'game_id': 'nioh3_pc', 'id': 'integration.test',
                'name': 'Integration test', 'version': '1.0',
                'dependencies': [], 'conflicts': [],
            }))
            archive.writestr('1234abcd.g1t', b'procedural texture bytes')
        notice = self.app.show_nexus_mods()
        selected = next(label for label, game in notice._game_by_label.items() if game.domain == 'nioh3')
        notice.game_var.set(selected)
        notice.refresh_capability()
        self.assertEqual(str(notice.import_button['state']), 'normal')
        with patch('tkinter.filedialog.askopenfilename', return_value=str(package)), \
                patch.object(mod_manager.ModManager, 'install_mod', side_effect=AssertionError('automatic install')), \
                patch.object(mod_manager.ModManager, 'apply_profile', side_effect=AssertionError('automatic apply')):
            notice.import_button.invoke()
        manager = self.app.mod_manager.manager
        self.assertEqual(manager.game_id, 'nioh3_pc')
        mod, = manager.mods()
        self.assertEqual(mod.id, 'integration.test')
        self.assertFalse(mod.installed)
        self.assertIsNone(manager.current_game_root)
        notice.game_var.set('ONE PIECE: PIRATE WARRIORS 4')
        notice.refresh_capability()
        self.assertEqual(str(notice.import_button['state']), 'disabled')
        self.assertIn('no installation adapter', notice.capability.get())

    def test_workshop_callback_selects_exported_game_and_only_imports(self):
        project, context = make_workshop(self.folder, 'nioh3_pc')
        report = review_manager_package(project, context)
        package = self.folder / 'workshop.zip'
        export_manager_package(project, package, context, review_token=report['review_token'])
        workspace = self.app.show_mod_manager()
        self.assertEqual(workspace.manager.game_id, 'nioh2_pc')
        with patch.object(mod_manager.ModManager, 'install_mod', side_effect=AssertionError('automatic install')), \
                patch.object(mod_manager.ModManager, 'apply_profile', side_effect=AssertionError('automatic apply')):
            imported = self.app._receive_workshop_package(package)
        self.assertEqual(workspace.manager.game_id, 'nioh3_pc')
        self.assertEqual(imported.id, 'workshop.test')
        self.assertFalse(imported.installed)
        self.assertIsNone(workspace.manager.current_game_root)

    def test_browser_menu_routes_serve_real_assets_and_app_close_releases_listener(self):
        with patch('koei_editor.shared.browser_companions.webbrowser.open', return_value=True) as browser:
            for key in ('localization_studio', 'mod_sandbox'):
                menu_index = next(index for index in range(self.app.editing_tools_menu.index('end') + 1)
                                  if self.app.editing_tools_menu.type(index) != 'separator'
                                  and self.app.editing_tools_menu.entrycget(index, 'label') == self.app.tr(key))
                self.app.editing_tools_menu.invoke(menu_index)
        self.assertEqual(browser.call_count, 2)
        manager = self.app.browser_companions
        server = manager._server
        thread = manager._thread
        for call in browser.call_args_list:
            target = urlsplit(call.args[0])
            connection = http.client.HTTPConnection(target.hostname, target.port, timeout=2)
            try:
                connection.request('GET', target.path)
                response = connection.getresponse()
                body = response.read()
            finally:
                connection.close()
            self.assertEqual(response.status, 200)
            self.assertIn(b'<!doctype html>', body.lower())
        self.assertFalse(self.app.sessions)
        self.app.close()
        self.assertTrue(manager._closed)
        self.assertFalse(thread.is_alive())
        self.assertEqual(server.socket.fileno(), -1)

    def test_knowledge_views_remain_readable_at_minimum_window_german_large_text(self):
        self.app.language_choice.set(LANGUAGES['de'])
        self.app.change_language()
        self.app.text_size_choice.set('140%')
        self.app.change_text_size()
        self.root.update()
        encyclopedia = self.app.show_encyclopedia()
        self.root.update()
        line_height = tkfont.Font(root=self.root, font=encyclopedia.details.cget('font')).metrics('linespace')
        self.assertGreaterEqual(encyclopedia.details.winfo_height(), line_height * 3)
        self.assertGreaterEqual(encyclopedia.table.winfo_height(), line_height * 3)
        encyclopedia.search.set('Edelgard')
        encyclopedia.table.selection_set(encyclopedia.rows[0]['id'])
        encyclopedia._selected()
        self.assertIn('MIT', encyclopedia.details.get('1.0', 'end'))
        self.assertIn('Quellen', next(widget.cget('text') for widget, key in encyclopedia._labels if key == 'details'))
        analyzer = self.app.show_patch_analyzer()
        self.root.update()
        root_right = self.root.winfo_rootx() + self.root.winfo_width()
        root_bottom = self.root.winfo_rooty() + self.root.winfo_height()
        for button in (analyzer.compare_button, analyzer.json_button, analyzer.markdown_button):
            self.assertLessEqual(button.winfo_rootx() + button.winfo_width(), root_right)
            self.assertLessEqual(button.winfo_rooty() + button.winfo_height(), root_bottom)
        self.assertGreaterEqual(analyzer.preview.winfo_height(), line_height * 3)

    def test_invalid_manual_nexus_zip_reports_error_without_hidden_callback_failure(self):
        package = self.folder / 'invalid.zip'
        original = b'this is not a zip archive'
        package.write_bytes(original)
        notice = self.app.show_nexus_mods()
        notice.game_var.set('NIOH 2')
        notice.refresh_capability()
        with patch('tkinter.filedialog.askopenfilename', return_value=str(package)), \
                patch('tkinter.messagebox.showerror') as error:
            notice.import_button.invoke()
        error.assert_called_once()
        self.assertFalse(self.callback_errors)
        self.assertEqual(package.read_bytes(), original)
        self.assertEqual(self.app.mod_manager.manager.mods(), ())


if __name__ == '__main__':
    unittest.main()
