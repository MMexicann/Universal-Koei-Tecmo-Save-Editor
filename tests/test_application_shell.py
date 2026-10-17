"""Shell navigation never edits saves and persists only bounded command IDs."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.application import Application, VERSION
from koei_editor.shared.command_palette import CommandEntry, search_commands
from koei_editor.shared.localization import CATALOGS, translate
from koei_editor.shared import shell_preferences as settings


class ShellPreferencesTests(unittest.TestCase):
    def test_longest_valid_namespaced_plugin_command_can_be_favorited(self):
        command = 'plugin:' + 'a.' + 'a' * 78 + ':' + 'b' * 80
        value = settings.toggle_favorite(settings.ShellPreferences(), command)
        self.assertEqual(value.favorites, (command,))
        self.assertEqual(settings.toggle_favorite(value, command).favorites, ())

    def test_settings_roundtrip_preserves_legacy_preferences_and_contains_no_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy = Path(directory) / 'preferences.json'
            legacy.write_text('{"schema":1,"theme":"Dark"}')
            value = settings.ShellPreferences('de', 140, ('game:dw3',), ('tool:comparison',))
            self.assertTrue(settings.save(value, settings.shell_path(legacy)))
            self.assertEqual(settings.load(settings.shell_path(legacy)), value)
            self.assertEqual(legacy.read_text(), '{"schema":1,"theme":"Dark"}')
            self.assertFalse(settings.save(replace(value, recent=('game:/private/save.dat',)), settings.shell_path(legacy)))
            self.assertEqual(settings.load(settings.shell_path(legacy)), value)

    def test_invalid_duplicate_or_oversized_data_falls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'shell.json'
            for raw in ('{"schema":1,"schema":1}', 'x' * (settings.MAX_BYTES + 1),
                        json.dumps({'schema': True, 'language': 'de', 'text_size': 100,
                                    'favorites': [], 'recent': []})):
                path.write_text(raw)
                self.assertEqual(settings.load(path), settings.ShellPreferences())

    def test_recents_are_bounded_unique_and_workspace_only(self):
        value = settings.ShellPreferences()
        for index in range(40):
            value = settings.remember(value, f'game:profile_{index}')
        value = settings.remember(value, 'game:profile_24')
        self.assertEqual(len(value.recent), settings.MAX_RECENT)
        self.assertEqual(value.recent[0], 'game:profile_24')
        self.assertEqual(settings.remember(value, 'command:save_copy'), value)
        self.assertEqual(settings.remember(value, 'C:/private/save.dat'), value)

    def test_catalogs_have_identical_keys_and_english_fallback(self):
        self.assertEqual(set(CATALOGS['en']), set(CATALOGS['de']))
        self.assertEqual(translate('choose', 'fr'), 'Choose your game')

    def test_search_matches_platforms_accents_favorites_and_stable_order(self):
        entries = (CommandEntry('game:a', 'Sophie', 'game', 'Windows PC'),
                   CommandEntry('tool:b', 'Vergleichen', 'tool'),
                   CommandEntry('game:c', 'Sophie', 'game', 'PlayStation 4'))
        self.assertEqual(search_commands(entries, 'sóphie pc'), (entries[0],))
        self.assertEqual(search_commands(entries, favorites=('game:c',), recent=('tool:b',)),
                         (entries[2], entries[1], entries[0]))
        self.assertFalse(search_commands(entries, 'missing'))


class ApplicationShellTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'preferences.json'
        self.app = Application(self.root, preferences_path=self.path, persist_preferences=False)
        self.root.geometry('1080x820')
        self.root.update()

    def tearDown(self):
        if hasattr(self, 'root'):
            self.root.destroy()
            self.directory.cleanup()

    def test_palette_keyboard_search_open_and_escape_restore_focus(self):
        self.app.library_search_entry.focus_force()
        self.root.update()
        self.root.event_generate('<Control-k>')
        self.root.update()
        palette = self.app.command_palette
        self.assertIsNotNone(palette)
        self.assertFalse(self.app.sessions)
        palette.query.set('dw7xl windows')
        self.assertEqual([entry.id for entry in palette.matches], ['game:dw7xl'])
        palette.window.event_generate('<Escape>')
        self.root.update()
        self.assertFalse(palette.window.winfo_exists())
        self.assertEqual(self.root.focus_get(), self.app.library_search_entry)
        self.assertFalse(self.app.sessions)

    def test_integrated_tool_commands_dispatch_exact_routes_and_remain_recent(self):
        calls = []
        routes = {'editing_presets': 'show_editing_presets', 'transfer': 'show_transfer',
                  'research_lab': 'show_research_lab', 'workflow_builder': 'show_workflow_builder'}
        for key, method in routes.items():
            setattr(self.app, method, lambda tool=key: calls.append(tool))
        self.app.open_command_palette()
        for key in routes:
            command_id = 'tool:' + key
            entries = self.app.command_entries()
            self.assertIn(command_id, {entry.id for entry in entries})
            self.app.command_palette.query.set(self.app.tr(key))
            self.assertIn(command_id, {entry.id for entry in self.app.command_palette.matches})
            self.app.execute_command(command_id)
            self.assertEqual(calls[-1], key)
            self.assertEqual(self.app.shell_settings.recent[0], command_id)
        self.app.command_palette.close()
        self.assertFalse(self.app.sessions)

    def test_language_change_preserves_integrated_workspace_and_breadcrumb(self):
        for key in ('editing_presets', 'research_lab', 'workflow_builder'):
            with self.subTest(workspace=key):
                self.app.show_library()
                self.app.library.pack_forget()
                frame = tk.Frame(self.app.workspace)
                frame.pack(fill='both', expand=True)
                marker = object()
                from types import SimpleNamespace
                tool = SimpleNamespace(frame=frame, pending=marker)
                setattr(self.app, key, tool)
                self.app.breadcrumb.set(self.app.tr(key))
                self.app.language_choice.set('Deutsch')
                self.app.change_language()
                self.root.update()
                self.assertEqual(self.app.breadcrumb.get(), self.app.tr(key))
                self.assertEqual(frame.winfo_manager(), 'pack')
                self.assertIs(tool.pending, marker)
                setattr(self.app, key, None)
                frame.destroy()
    def test_palette_executes_exact_profile_and_keeps_editor_state(self):
        editor = self.app.select_game('dw7xl')
        self.app.show_library()
        self.app.open_command_palette()
        palette = self.app.command_palette
        palette.query.set('dw7xl windows')
        palette.activate()
        self.assertEqual(self.app.active_game, 'dw7xl')
        self.assertIs(self.app.sessions['dw7xl'][1], editor)
        self.assertIsNone(editor.document)
        self.assertFalse(editor.changes)
        self.assertEqual(self.app.shell_settings.recent[0], 'game:dw7xl')

    def test_favorites_and_recents_are_searchable_without_paths(self):
        self.app._toggle_favorite('game:dw3')
        self.app._remember_workspace('tool:comparison')
        self.assertEqual([entry.id for entry in search_commands(self.app.command_entries(), 'favorites')], ['game:dw3'])
        self.assertEqual([entry.id for entry in search_commands(self.app.command_entries(), 'recent')], ['tool:comparison'])
        self.app.execute_command('tool:arbitrary_import')
        self.assertFalse(self.app.sessions)
        self.assertFalse(self.path.exists())
        self.assertFalse(self.app.shell_preferences_path.exists())

    def test_palette_respects_safety_dialog_grab(self):
        dialog = tk.Toplevel(self.root)
        dialog.grab_set()
        self.app.open_command_palette()
        self.assertIsNone(self.app.command_palette)
        self.assertEqual(self.root.grab_current(), dialog)
        dialog.destroy()

    def test_repeated_palette_close_releases_query_callbacks(self):
        for _index in range(10):
            self.app.open_command_palette()
            palette = self.app.command_palette
            self.assertEqual(len(palette.query.trace_info()), 1)
            palette.close()
            self.assertEqual(palette.query.trace_info(), [])
        self.assertFalse(self.app.sessions)

    def test_enabled_plugin_commands_open_only_inert_help_content(self):
        from types import SimpleNamespace
        center = SimpleNamespace(
            plugin_commands=lambda: [('sample.docs:guide', 'Sample guide', 'Read-only community documentation')],
            open_plugin_command=lambda key: opened.append(key))
        opened = []
        self.app.help_center = center
        commands = self.app.command_entries()
        self.assertEqual([entry.id for entry in search_commands(commands, 'sample guide')], ['plugin:sample.docs:guide'])
        with patch.object(self.app, 'show_help') as show:
            self.app.execute_command('plugin:sample.docs:guide')
            show.assert_called_once_with('plugins')
        self.assertEqual(opened, ['sample.docs:guide'])
        self.app.execute_command('plugin:unapproved')
        self.assertEqual(opened, ['sample.docs:guide'])
        self.app.help_center = None

    def test_german_shell_and_text_size_do_not_replace_retained_editor(self):
        editor = self.app.select_game('dw7xl')
        self.app.language_choice.set('Deutsch')
        self.app.change_language()
        self.assertEqual(self.app.home_button.cget('text'), '‹ Spielebibliothek')
        self.app.text_size_choice.set('140%')
        self.app.change_text_size()
        self.assertEqual(self.app.shell_settings.text_size, 140)
        self.assertIs(self.app.sessions['dw7xl'][1], editor)
        self.assertIsNone(editor.document)
        self.assertEqual(VERSION, '2.7')

    def test_navigation_wraps_and_stays_reachable_at_small_size(self):
        self.app.language_choice.set('Deutsch')
        self.app.change_language()
        self.app.text_size_choice.set('140%')
        self.app.change_text_size()
        self.root.geometry('780x680')
        self.root.update()
        for widget in (*self.app._navigation_buttons, self.app.language_selector, self.app.text_size_selector):
            self.assertTrue(widget.winfo_ismapped())
            self.assertGreaterEqual(widget.winfo_rootx(), self.root.winfo_rootx())
            self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(), self.root.winfo_rootx() + self.root.winfo_width())
        self.assertEqual(self.app._library_columns[self.app.platform_choice.get()], 2)

    def test_search_bursts_coalesce_and_enter_flushes_latest_query(self):
        with patch.object(self.app, 'show_platform', wraps=self.app.show_platform) as show:
            for text in ('d', 'dw', 'dw7', 'dw7xl'):
                self.app.library_search.set(text)
            self.assertEqual(show.call_count, 0)
            self.root.update()
            self.assertEqual(show.call_count, 1)
        self.app.platform_choice.set('Windows PC')
        self.app.library_search.set('dw7xl')
        self.app.open_library_match()
        self.assertEqual(self.app.active_game, 'dw7xl')

    def test_real_help_workspace_and_late_panels_follow_text_size_and_locale(self):
        from tkinter import font
        self.app.text_size_choice.set('140%')
        self.app.change_text_size()
        self.app.show_help('compatibility')
        center = self.app.help_center
        self.assertEqual(len(center.matrix.get_children()), len(self.app.library_games))
        self.assertEqual(font.Font(self.root, font=center.compatibility_detail.cget('font')).actual('size'), 14)
        self.app.show_help('validation')
        panel = center._panels['validation']
        record = panel.record
        self.assertEqual(font.Font(self.root, font=panel.preview.cget('font')).actual('size'), 14)
        self.app.language_choice.set('Deutsch')
        self.app.change_language()
        self.assertIs(panel.record, record)
        self.assertEqual(panel.language, 'de')
        self.app.show_library()
        self.app.execute_command('tool:validation')
        self.assertIs(self.app.help_center, center)
        self.assertIs(panel.record, record)

    def test_real_approved_plugin_appears_in_palette_and_disable_revokes_dispatch(self):
        from tests.test_help_center_integration import integration_manifest
        self.app.show_help('plugins')
        panel = self.app.help_center._panels['plugins']
        directory = Path(self.directory.name) / 'plugins'
        directory.mkdir()
        (directory / 'integration.plugin.json').write_text(json.dumps(integration_manifest()))
        self.assertTrue(panel.load_directory(directory))
        self.assertFalse(any(entry.category == 'plugin' for entry in self.app.command_entries()))
        panel.reviewed.set(True)
        panel.enable_selected()
        entry = next(entry for entry in self.app.command_entries() if entry.category == 'plugin')
        self.app.open_command_palette()
        palette = self.app.command_palette
        palette.query.set(entry.id)
        self.assertEqual(len(palette.matches), 1)
        palette.activate()
        self.assertIn('EnglishCommunityMarker', panel.preview.get('1.0', 'end'))
        panel.tree.selection_set('0')
        panel._select()
        panel.disable_selected()
        self.assertNotIn(entry.id, {item.id for item in self.app.command_entries()})
        self.assertIsNone(self.app.execute_command(entry.id))


if __name__ == '__main__':
    unittest.main()
