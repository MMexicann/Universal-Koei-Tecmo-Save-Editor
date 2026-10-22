"""Shell navigation never edits saves and persists only bounded command IDs."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import Mock, patch

from koei_editor.application import Application, VERSION
from koei_editor.shared.command_palette import CommandEntry, search_commands
from koei_editor.shared.localization import CATALOGS, translate
from koei_editor.shared import shell_preferences as settings


class ShellPreferencesTests(unittest.TestCase):
    def test_show_mod_manager_attaches_workspace_to_existing_download_handoff_seam(self):
        from types import SimpleNamespace
        from koei_editor.shared import mod_manager_gui

        workspace = object()
        attach = Mock()
        shell = SimpleNamespace(
            mod_manager=None,
            root=object(),
            workspace=object(),
            set_mod_manager_download_handoff=attach,
            _show_editing_tool=Mock(),
            _remember_workspace=Mock(),
            tr=lambda key: key,
        )
        with patch.object(mod_manager_gui, 'ModManagerWorkspace', return_value=workspace):
            result = Application.show_mod_manager(shell)

        self.assertIs(result, workspace)
        attach.assert_called_once_with(workspace)
        shell._show_editing_tool.assert_called_once_with(workspace, 'mod_manager')
        shell._remember_workspace.assert_called_once_with('tool:mod_manager')

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


class MenuTranslationTests(unittest.TestCase):
    class Menu:
        def __init__(self, labels):
            self.labels = list(labels)

        def index(self, end):
            return len(self.labels) - 1 if self.labels else None

        def entrycget(self, index, option):
            if option != 'label':
                raise AssertionError(option)
            return self.labels[index]

        def entryconfigure(self, index, **options):
            self.labels[index] = options['label']

    def test_named_menu_entries_translate_after_other_routes_shift_indices(self):
        menu = self.Menu((CATALOGS['en']['editing_presets'], CATALOGS['en']['transfer'], '',
                          CATALOGS['en']['research_lab'], CATALOGS['en']['research_import'], '',
                          'Game Asset Explorer', CATALOGS['en']['emulator_hub']))

        class Shell:
            editing_tools_menu = menu

            @staticmethod
            def tr(key):
                return translate(key, 'de')

        Application._refresh_editing_menu_labels(Shell())

        self.assertEqual(menu.labels[0], translate('editing_presets', 'de'))
        self.assertEqual(menu.labels[5], '')
        self.assertEqual(menu.labels[6], translate('asset_explorer', 'de')
                         if 'asset_explorer' in CATALOGS['de'] else 'Game Asset Explorer')
        self.assertEqual(menu.labels[7], translate('emulator_hub', 'de'))


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
            if self.root is not None:
                browser = getattr(self.app, 'nexus_mods', None)
                if browser is not None:
                    browser.close()
                if hasattr(self, '_original_scaling'):
                    self.root.tk.call('tk', 'scaling', self._original_scaling)
                self.root.destroy()
            self.directory.cleanup()

    def _use_native_scaling(self, scaling):
        self._original_scaling = self.root.tk.call('tk', 'scaling')
        self.root.destroy()
        self.root = tk.Tk()
        self.root.tk.call('tk', 'scaling', scaling)
        self.app = Application(self.root, preferences_path=self.path, persist_preferences=False)
        self.root.geometry('1080x820')
        self.root.update()

    def test_active_editor_uses_one_header_row_and_restores_full_navigation(self):
        editor = self.app.select_game('dw7xl')
        self.root.geometry('800x680')
        self.root.update()
        self.assertLessEqual(self.app._shell_top.winfo_height(), 60)
        self.assertFalse(self.app.theme_selector.winfo_ismapped())
        for widget in (self.app.compact_home_button, self.app.compact_help_button, self.app.command_button,
                       self.app.session_selector):
            self.assertTrue(widget.winfo_ismapped())
        self.app.show_library()
        self.root.update()
        self.assertTrue(self.app.theme_selector.winfo_ismapped())
        self.assertTrue(self.app.converter_button.winfo_ismapped())
        self.app.select_game('dw7xl')
        self.app.show_help()
        self.root.update()
        self.assertTrue(self.app.language_selector.winfo_ismapped())
        self.assertIs(self.app.sessions['dw7xl'][1], editor)

    def test_compact_header_palette_keeps_language_text_size_and_appearance_available(self):
        editor = self.app.select_game('dw7xl')
        self.root.geometry('780x680')
        for command in ('language_de', 'text_size_140', 'theme_dark'):
            self.assertIn('command:' + command, {entry.id for entry in self.app.command_entries()})
            self.app.execute_command('command:' + command)
        self.root.update()
        self.assertEqual(self.app.language, 'de')
        self.assertEqual(self.app.shell_settings.text_size, 140)
        self.assertEqual(self.app.theme_name.get(), 'Dark')
        self.assertLessEqual(self.app._shell_top.winfo_height(), 70)
        self.assertEqual(self.app.active_game, 'dw7xl')
        self.assertIs(self.app.sessions['dw7xl'][1], editor)
        self.assertFalse(editor.changes)
        for widget in (self.app.compact_home_button, self.app.compact_help_button, self.app.command_button,
                       self.app.session_selector):
            self.assertTrue(widget.winfo_ismapped())
            self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                 self.root.winfo_rootx() + self.root.winfo_width())

    def test_compact_session_switch_and_help_keep_pending_edits_and_editor_instances(self):
        from tests.test_origins_parser import fixture
        source = Path(self.directory.name) / 'copy.dat'
        source.write_bytes(fixture())
        editor = self.app.select_game('origins')
        self.assertTrue(editor.open_path(source))
        editor.stage_values({'gold': 4321})
        pending, history = dict(editor.changes), list(editor.history)
        other = self.app.select_game('dw7xl')
        self.root.update()
        self.assertTrue(self.app.session_selector.winfo_viewable())
        self.app.session_choice.set(next(label for label, game_id in self.app._session_labels.items()
                                         if game_id == 'origins'))
        self.app.resume_session()
        self.root.update()
        self.assertEqual(self.app.active_game, 'origins')
        self.assertIs(self.app.sessions['origins'][1], editor)
        self.assertIs(self.app.sessions['dw7xl'][1], other)
        self.app.compact_help_button.invoke()
        self.root.update()
        self.assertTrue(self.app.help_center.frame.winfo_viewable())
        self.assertTrue(self.app.language_selector.winfo_viewable())
        self.assertEqual((editor.changes, editor.history), (pending, history))
        self.assertEqual(source.read_bytes(), fixture())

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
                  'mod_manager': 'show_mod_manager', 'research_lab': 'show_research_lab',
                  'workflow_builder': 'show_workflow_builder', 'emulator_hub': 'show_emulator_hub'}
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

    def test_nexus_browser_is_a_localized_tool_and_uses_active_pc_game(self):
        self.app.select_game('pw4')
        browser = self.app.show_nexus_mods()
        self.root.update()
        self.assertIs(browser, self.app.nexus_mods)
        self.assertEqual(browser._selected_game().game_id, 'pw4')
        self.assertFalse(browser._client.has_api_key)
        self.assertEqual(str(browser.manager_button['state']), 'disabled')
        self.assertEqual(self.app.editing_tools_menu.entrycget(6, 'label'), 'Nexus Mods')
        self.assertIn('tool:nexus_mods', {entry.id for entry in self.app.command_entries()})
        self.app.language_choice.set('Deutsch')
        self.app.change_language()
        self.root.update()
        self.assertEqual(browser.title_label.cget('text'), 'Nexus-Mods-Browser')
        self.assertEqual(self.app.editing_tools_menu.entrycget(6, 'label'), 'Nexus Mods')

    def test_language_change_preserves_integrated_workspace_and_breadcrumb(self):
        for key in ('editing_presets', 'mod_manager', 'research_lab', 'workflow_builder', 'emulator_hub'):
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

    def test_emulator_hub_opens_as_retained_tool_and_survives_language_change(self):
        hub = self.app.show_emulator_hub()
        self.root.update()
        self.assertIs(self.app.emulator_hub, hub)
        self.assertIn(hub, self.app._tool_workspaces())
        self.assertEqual(self.app.breadcrumb.get(), self.app.tr('emulator_hub'))
        self.assertIs(hub.open_saved_copy.__self__, self.app)
        self.assertIs(hub.open_saved_copy.__func__, Application.open_saved_copy)
        self.app.language_choice.set('Deutsch')
        self.app.change_language()
        self.root.update()
        self.assertIs(self.app.emulator_hub, hub)
        self.assertEqual(self.app.breadcrumb.get(), self.app.tr('emulator_hub'))
        self.assertEqual(hub.frame.winfo_manager(), 'pack')

    def test_mod_manager_is_a_retained_command_and_localized_menu_tool(self):
        from koei_editor.shared.localization import CATALOGS
        self.assertEqual(set(CATALOGS['en']), set(CATALOGS['de']))
        self.assertIn('tool:mod_manager', {entry.id for entry in self.app.command_entries()})
        index = self.app._editing_tools_menu_index('mod_manager')
        self.assertEqual(self.app.editing_tools_menu.entrycget(index, 'label'), 'Koei Tecmo Mod Manager')
        self.app.language_choice.set('Deutsch')
        self.app.change_language()
        index = self.app._editing_tools_menu_index('mod_manager')
        self.assertEqual(self.app.editing_tools_menu.entrycget(index, 'label'), 'Koei-Tecmo-Mod-Manager')

    def test_mod_manager_workspace_is_constructed_once_with_temporary_state(self):
        from koei_editor.shared import mod_manager_gui
        from types import SimpleNamespace
        state_dir = (Path(self.directory.name) / 'mod_manager').resolve()
        attach_handoff = Mock()
        self.app.set_mod_manager_download_handoff = attach_handoff
        with patch.object(mod_manager_gui, 'preference_path', return_value=self.path):
            workspace = self.app.show_mod_manager()
            attach_handoff.assert_called_once_with(workspace)
            self.assertIsInstance(workspace, mod_manager_gui.ModManagerWorkspace)
            self.assertIs(self.app.mod_manager, workspace)
            self.assertEqual(workspace.manager.state_dir, state_dir)
            self.assertIsNone(workspace.manager.current_game_root)
            self.assertIn(workspace, self.app._tool_workspaces())
            self.assertEqual(workspace.frame.winfo_manager(), 'pack')

            self.app.show_library()
            self.assertEqual(workspace.frame.winfo_manager(), '')
            self.assertIs(self.app.show_mod_manager(), workspace)
            self.assertEqual(attach_handoff.call_count, 2)
            self.assertEqual(workspace.frame.winfo_manager(), 'pack')

            candidate = str(Path(self.directory.name) / 'unreadable-game')
            prior_root = Path(self.directory.name) / 'prior-game'
            workspace.manager.current_game_root = prior_root
            with (patch.object(mod_manager_gui.filedialog, 'askdirectory', return_value=candidate),
                  patch.object(workspace.manager, 'set_game_root', side_effect=OSError('recovery failed')),
                  patch.object(workspace.manager, 'has_pending_transaction_for', return_value=True),
                  patch.object(workspace, '_error')):
                workspace.choose_game_root()
            workspace._mods['test-mod'] = SimpleNamespace(installed=False)
            workspace.mod_table.insert('', 'end', iid='test-mod', text='Test mod')
            workspace.mod_table.selection_set('test-mod')
            workspace._update_controls()
            self.assertEqual(str(workspace.create_profile_button.cget('state')), 'disabled')
            self.assertEqual(str(workspace.import_button.cget('state')), 'disabled')
            self.assertEqual(str(workspace.remove_button.cget('state')), 'disabled')
            workspace.refresh()
            self.assertTrue(workspace._recovery_blocked)
            self.assertEqual(str(workspace.create_profile_button.cget('state')), 'disabled')

            def select_candidate(path):
                workspace.manager.current_game_root = Path(path)
                return Path(path)
            with (patch.object(mod_manager_gui.filedialog, 'askdirectory', return_value=candidate),
                  patch.object(workspace.manager, 'set_game_root', side_effect=select_candidate),
                  patch.object(workspace, '_error')):
                workspace.choose_game_root()
            self.assertFalse(workspace._recovery_blocked)
            self.assertEqual(str(workspace.create_profile_button.cget('state')), 'normal')
            self.assertEqual(str(workspace.import_button.cget('state')), 'normal')
            self.assertEqual(str(workspace.remove_button.cget('state')), 'normal')

        self.assertTrue(str(workspace.manager.state_dir).startswith(self.directory.name))
        self.assertFalse((state_dir / 'library.json').exists())

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
        self.assertEqual(VERSION, '3.1')

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

    def test_compact_editor_header_retains_controls_pending_state_and_library_navigation(self):
        from tests.test_origins_parser import fixture
        source = Path(self.directory.name) / 'copy.dat'
        source.write_bytes(fixture())
        editor = self.app.select_game('origins')
        self.assertTrue(editor.open_path(source))
        editor.stage_values({'gold': 4321})
        editor.workspace_tabs.select(editor.edit_page)
        self.root.update()
        pending, history = dict(editor.changes), list(editor.history)
        self.assertGreater(editor.fields.winfo_height(), 220)
        self.assertLess(self.app._shell_top.winfo_height(), 70)
        self.assertFalse(self.app.navigation.winfo_ismapped())
        self.app.shell_controls_button.focus_force()
        self.root.update()
        self.app.shell_controls_button.event_generate('<KeyPress-space>')
        self.app.shell_controls_button.event_generate('<KeyRelease-space>')
        self.root.update()
        for widget in (*self.app._navigation_buttons, self.app.theme_selector,
                       self.app.language_selector, self.app.text_size_selector):
            self.assertTrue(widget.winfo_viewable())
        self.app.shell_controls_button.invoke()
        self.root.update()
        self.assertGreater(editor.fields.winfo_height(), 220)
        self.app.compact_home_button.invoke()
        self.root.update()
        self.assertIsNone(self.app.active_game)
        self.assertTrue(self.app.navigation.winfo_ismapped())
        self.assertTrue(self.app.language_selector.winfo_ismapped())
        self.assertFalse(self.app.shell_controls_button.winfo_ismapped())
        self.assertIs(self.app.select_game('origins'), editor)
        # Qualify the tall layout even on runners with a smaller native workarea.
        self.root.maxsize(1800, 1400)
        self.root.geometry('1180x930')
        self.root.update()
        self.assertGreaterEqual(self.root.winfo_height(), 900)
        self.assertTrue(self.app.navigation.winfo_ismapped())
        self.assertFalse(self.app.shell_controls_button.winfo_ismapped())
        self.assertEqual((editor.changes, editor.history), (pending, history))
        self.assertEqual(source.read_bytes(), fixture())

    def test_compact_editor_navigation_fits_both_languages_themes_and_larger_text(self):
        self.app.select_game('origins')
        self.root.minsize(650, 500)
        self.root.geometry('800x650')
        self.app.text_size_choice.set('140%')
        self.app.change_text_size()
        for language in ('English', 'Deutsch'):
            self.app.language_choice.set(language)
            self.app.change_language()
            for theme in ('Light', 'Dark'):
                self.app.apply_theme(theme)
                self.root.update()
                for widget in (self.app.command_button, self.app.compact_home_button,
                               self.app.compact_help_button, self.app.session_selector,
                               self.app.shell_controls_button):
                    self.assertTrue(widget.winfo_viewable())
                    self.assertGreaterEqual(widget.winfo_width(), widget.winfo_reqwidth())
                    self.assertGreaterEqual(widget.winfo_rootx(), self.root.winfo_rootx())
                    self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                         self.root.winfo_rootx() + 800)
                self.app.shell_controls_button.invoke()
                self.root.update()

                for widget in (*self.app._navigation_buttons, self.app.theme_selector,
                               self.app.language_selector, self.app.text_size_selector,
                               self.app.session_selector,
                               self.app.shell_controls_button):
                    self.assertTrue(widget.winfo_viewable())
                    self.assertGreaterEqual(widget.winfo_width(), widget.winfo_reqwidth())
                    self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                         self.root.winfo_rootx() + 800)
                self.app.shell_controls_button.invoke()
                self.root.update()

    def test_embedded_file_actions_keep_their_full_width_at_each_text_size(self):
        for game_id in ('origins', 'dw3'):
            editor = self.app.select_game(game_id)
            buttons = getattr(editor, 'save_buttons', ()) or editor.buttons
            row = buttons[0].master
            for size in ('100%', '120%', '140%'):
                with self.subTest(game=game_id, size=size):
                    self.root.geometry('780x680')
                    self.app.text_size_choice.set(size)
                    self.app.change_text_size()
                    self.root.update()
                    for widget in row.winfo_children():
                        if not isinstance(widget, ttk.Button):
                            continue
                        self.assertTrue(widget.winfo_viewable())
                        self.assertGreaterEqual(widget.winfo_width(), widget.winfo_reqwidth())
                        self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                             self.root.winfo_rootx() + self.root.winfo_width())
                    self.assertFalse(editor.changes)
            self.app.show_library()
            self.root.update()
            self.assertEqual(self.root.minsize(), (780, 680))

    def test_editor_width_fitting_respects_explicit_compact_minimum(self):
        self.root.minsize(650, 500)
        self.root.geometry('800x650')
        self.app.select_game('origins')
        self.app.text_size_choice.set('140%')
        self.app.change_text_size()
        self.root.update()
        self.assertEqual(self.root.minsize(), (650, 500))
        self.assertEqual(self.root.winfo_width(), 800)

    def test_native_scaling_reserves_field_and_dashboard_viewports_without_changing_preferences(self):
        from tests.test_origins_parser import fixture
        self._use_native_scaling(1.8)
        source = Path(self.directory.name) / 'copy.dat'
        source.write_bytes(fixture())
        editor = self.app.select_game('origins')
        self.assertTrue(editor.open_path(source))
        editor.stage_values({'gold': 4321})
        pending, history = dict(editor.changes), list(editor.history)
        editor.workspace_tabs.select(editor.edit_page)
        self.root.update()
        self.assertGreater(editor.fields.winfo_height(), 220)
        minimum = self.root.minsize()
        for _ in range(3):
            self.root.update()
            self.assertEqual(self.root.minsize(), minimum)
        editor.workspace_tabs.select(editor.dashboard_page)
        self.root.update()
        self.assertGreater(editor.dashboard_view.canvas.winfo_height(), 100)
        editor.workspace_tabs.select(editor.edit_page)
        self.root.update()
        self.assertGreater(editor.fields.winfo_height(), 220)
        self.assertEqual(self.app.shell_settings.text_size, 100)
        self.assertAlmostEqual(float(self.root.tk.call('tk', 'scaling')), 1.8, delta=0.02)
        self.assertEqual((editor.changes, editor.history), (pending, history))
        self.assertEqual(source.read_bytes(), fixture())
        self.app.show_library()
        self.root.update()
        self.assertEqual(self.root.minsize(), (780, 680))

    def test_native_scaling_height_guard_preserves_explicit_embedding_minimum(self):
        self._use_native_scaling(1.8)
        self.root.minsize(650, 500)
        self.root.update()
        original_height = self.root.winfo_height()
        editor = self.app.select_game('origins')
        editor.workspace_tabs.select(editor.edit_page)
        self.root.update()
        editor.workspace_tabs.select(editor.dashboard_page)
        self.root.update()
        self.assertEqual(self.root.minsize(), (650, 500))
        self.assertEqual(self.root.winfo_height(), original_height)

    def test_compact_editor_fits_native_workarea_without_changing_fonts_or_pending_edits(self):
        from tests.test_origins_parser import fixture
        self._use_native_scaling(1.333005)
        self.root.maxsize(1028, 729)
        self.root.geometry('1080x820')
        source = Path(self.directory.name) / 'copy.dat'
        source.write_bytes(fixture())
        editor = self.app.select_game('origins')
        self.assertTrue(editor.open_path(source))
        editor.stage_values({'gold': 4321})
        editor.workspace_tabs.select(editor.dashboard_page)
        self.root.update()
        self.assertEqual(tuple(map(int, editor.header.cget('padding'))), (18, 2))
        editor.workspace_tabs.select(editor.edit_page)
        self.root.update()
        pending, history = dict(editor.changes), list(editor.history)
        self.assertLessEqual(self.root.winfo_height(), 729)
        self.assertGreater(editor.fields.winfo_height(), 220)
        self.assertTrue(editor.details_toggle.winfo_viewable())
        self.assertEqual(self.app.shell_settings.text_size, 100)
        editor.workspace_tabs.select(editor.dashboard_page)
        self.root.maxsize(1800, 1400)
        self.root.geometry('1180x930')
        self.root.update()
        self.assertEqual(tuple(map(int, editor.header.cget('padding'))), (18, 10))
        self.assertEqual((editor.changes, editor.history), (pending, history))
        self.assertEqual(source.read_bytes(), fixture())

    def test_editor_fit_does_not_reenter_while_processing_queued_geometry_work(self):
        editor = self.app.select_game('origins')
        editor.workspace_tabs.select(editor.edit_page)
        self.root.update()
        original_fit = self.app._fit_editor_actions
        depth, maximum = 0, 0
        def track_fit():
            nonlocal depth, maximum
            depth += 1
            maximum = max(maximum, depth)
            try:
                original_fit()
            finally:
                depth -= 1
        with patch.object(self.app, '_fit_editor_actions', track_fit):
            self.app._schedule_editor_width()
            self.root.after_idle(self.app._schedule_editor_width)
            self.root.update()
        self.assertEqual(maximum, 1)
        self.assertGreater(editor.fields.winfo_height(), 220)

    def test_height_fit_converges_across_full_header_boundary_and_cancels_callbacks(self):
        self._use_native_scaling(2.0)
        editor = self.app.select_game('origins')
        editor.workspace_tabs.select(editor.edit_page)
        self.root.update()
        self.assertGreaterEqual(self.root.winfo_height(), 900)
        self.assertTrue(self.app.navigation.winfo_viewable())
        self.assertGreater(editor.fields.winfo_height(), 220)
        minimum = self.root.minsize()
        for _ in range(3):
            self.root.update()
            self.assertEqual(self.root.minsize(), minimum)
        self.app._schedule_editor_width()
        self.app._schedule_navigation()
        self.root.tk.call('tk', 'scaling', self._original_scaling)
        self.root.destroy()
        self.root = None
        self.assertIsNone(self.app._editor_width_after)
        self.assertIsNone(self.app._navigation_after)

    def test_help_search_shortcut_targets_the_visible_tab_and_preserves_drafts(self):
        self.app.show_help('help')
        center = self.app.help_center
        self.root.focus_force()
        for tab, attribute in (('help', 'help_search'), ('compatibility', 'compatibility_search'),
                               ('workflows', 'guide_selector'), ('plugins', None)):
            center.notebook.select(center.tabs[tab])
            self.root.update()
            self.root.event_generate('<Control-f>')
            self.root.update()
            target = getattr(center, attribute) if attribute else center._panels['plugins'].search_entry
            self.assertIs(self.root.focus_get(), target)
            self.assertTrue(target.winfo_viewable())
        center.notebook.select(center.tabs['validation'])
        self.root.update()
        panel = center._panels['validation']
        panel.revision.set('29')
        self.root.event_generate('<Control-f>')
        self.root.update()
        self.assertIs(self.root.focus_get(), center.notebook)
        self.assertEqual(center.selected_tab(), 'validation')
        self.assertIs(center._panels['validation'], panel)
        self.assertEqual(panel.revision.get(), '29')
        self.assertFalse(self.app.library.winfo_ismapped())

    def test_direct_help_tab_selection_updates_navigation_and_ignores_hidden_tabs(self):
        self.app.show_help('help')
        center = self.app.help_center
        center.notebook.select(center.tabs['compatibility'])
        self.root.update()
        self.assertEqual(self.app.breadcrumb.get(), self.app.tr('compatibility'))
        self.assertEqual(self.app.shell_settings.recent[0], 'tool:compatibility')
        self.app.language_choice.set('Deutsch')
        self.app.change_language()
        self.root.update()
        self.assertEqual(self.app.breadcrumb.get(), self.app.tr('compatibility'))
        self.app.select_game('origins')
        self.root.update()
        breadcrumb, recent = self.app.breadcrumb.get(), self.app.shell_settings.recent
        center.notebook.select(center.tabs['help'])
        self.root.update()
        self.assertEqual(self.app.active_game, 'origins')
        self.assertEqual(self.app.breadcrumb.get(), breadcrumb)
        self.assertEqual(self.app.shell_settings.recent, recent)
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
