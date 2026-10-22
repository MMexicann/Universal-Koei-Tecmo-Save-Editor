"""Real Tk workflows for the source-verified configuration manager."""
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.application import Application
from koei_editor.shared import configuration_manager as backend
from koei_editor.shared.configuration_gui import ConfigurationWorkspace


GAME_FIXTURE = (
    b'; fixture only\r\n[Window]\r\nFullScreen=0\r\n'
    b'[Lang]\r\nLanguage=2\r\n[Graphics]\r\nOutline=1\r\n'
    b'ScreenWidth=1920\r\nScreenHeight=1080\r\nUnknownVendorKey=keep\r\n'
)

MOD_FIXTURE = (
    b'; mod fixture only\r\n[Rendering]\r\nShadowMultiplier=2\r\n'
    b'SMAA=1\r\nSharpen=30\r\n[Battle]\r\nBattleCutInShadows=1\r\n'
    b'BattleCutInDimming=0\r\n[Startup]\r\nSkipLogos=0\r\n'
    b'SkipIntroMovie=1\r\n[Launcher]\r\nSkipLauncher=0\r\n'
    b'[Diagnostics]\r\nVerboseLogging=0\r\n[Unknown]\r\nKeep=yes\r\n'
)


class ConfigurationWorkspaceTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.root.destroy)
        self.root.withdraw()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.file = self.folder / backend.FORMAT_FILENAME
        self.file.write_bytes(GAME_FIXTURE)
        self.workspace = ConfigurationWorkspace(self.root, self.root)
        self._storage = self.folder / 'private-config-data'

    def open_game_fixture(self):
        self.workspace.game.set(self.workspace._game_labels['arland_rorona_dx'])
        self.workspace.path.set(str(self.file))
        with patch.object(backend, 'configuration_data_dir', return_value=self._storage):
            self.workspace.open_file()

    def test_inspect_stage_save_and_automatic_backup_preserve_opaque_bytes(self):
        self.open_game_fixture()
        self.assertEqual(self.workspace.document.game_id, 'arland_rorona_dx')
        self.assertEqual(self.workspace.settings.set('screen_width', 'access'), 'Read-only')
        self.workspace.settings.selection_set('fullscreen')
        self.workspace.select_setting()
        self.workspace.value_choice.set('On')
        self.workspace.stage_value()
        self.assertEqual(self.workspace.settings.set('fullscreen', 'pending'), 'On')
        with patch.object(backend, 'configuration_data_dir', return_value=self._storage):
            self.workspace.save()
            backups = backend.list_backups(game_id='arland_rorona_dx')
        self.assertEqual(len(backups), 1)
        self.assertEqual(self.file.read_bytes(), GAME_FIXTURE.replace(b'FullScreen=0', b'FullScreen=1'))
        self.assertIn(b'UnknownVendorKey=keep\r\n', self.file.read_bytes())
        self.assertIn('Saved and read back', self.workspace.status.get())

    def test_profiles_stage_review_compatible_values_and_restore_exact_backup(self):
        self.open_game_fixture()
        with patch.object(backend, 'configuration_data_dir', return_value=self._storage):
            backup = backend.create_backup(self.workspace.document)
            profile_source = self.folder / 'profile-source'
            profile_source.mkdir()
            profile_path = profile_source / backend.FORMAT_FILENAME
            profile_path.write_bytes(GAME_FIXTURE.replace(b'FullScreen=0', b'FullScreen=1'))
            profile_document = backend.inspect_config(profile_path, 'arland_rorona_dx')
            saved = backend.create_profile(profile_document, 'full screen')
            self.workspace._refresh_records()
            self.workspace.profile_choice.set(self.workspace._profile_labels[saved.id])
            self.workspace.apply_profile()
            self.assertEqual(self.workspace.staged, {'fullscreen': 1})

            # A profile belongs to its game and cannot be applied to a different one.
            other = self.folder / 'other-title' / backend.MOD_FORMAT_FILENAME
            other.parent.mkdir()
            other.write_bytes(MOD_FIXTURE)
            other_doc = backend.inspect_config(other, 'arland_rorona_dx')
            with self.assertRaises(backend.IncompatibleConfigurationError):
                backend.apply_profile(other_doc, saved)

            self.file.write_bytes(GAME_FIXTURE.replace(b'FullScreen=0', b'FullScreen=1'))
            self.workspace.document = backend.inspect_config(self.file, 'arland_rorona_dx')
            self.workspace.staged.clear()
            self.workspace._refresh_records()
            self.workspace.backup_choice.set(self.workspace._backup_labels[backup.id])
            with patch('koei_editor.shared.configuration_gui.messagebox.askyesno', return_value=True):
                self.workspace.restore_backup()
        self.assertEqual(self.file.read_bytes(), GAME_FIXTURE)
        self.assertIn('exact bytes were verified', self.workspace.status.get())

    def stage_fullscreen(self):
        self.open_game_fixture()
        self.workspace.settings.selection_set('fullscreen')
        self.workspace.select_setting()
        self.workspace.value_choice.set('On')
        self.workspace.stage_value()
        self.assertEqual(self.workspace.staged, {'fullscreen': 1})

    def test_application_close_keeps_staged_configuration_when_discard_is_cancelled(self):
        self.stage_fullscreen()
        app = Application(self.root, persist_preferences=False,
                          preferences_path=self.folder / 'preferences.json')
        app.game_configuration = self.workspace
        with patch('koei_editor.shared.configuration_gui.messagebox.askyesno', return_value=False) as ask, \
                patch.object(self.root, 'destroy') as destroy:
            app.close()
            ask.assert_called_once()
            destroy.assert_not_called()
        self.assertEqual(self.workspace.staged, {'fullscreen': 1})
        self.assertEqual(self.file.read_bytes(), GAME_FIXTURE)
        with patch('koei_editor.shared.configuration_gui.messagebox.askyesno', return_value=True), \
                patch.object(self.root, 'destroy') as destroy:
            app.close()
            destroy.assert_called_once()

    def test_cancelled_selection_change_restores_path_game_and_pending_values(self):
        self.stage_fullscreen()
        document = self.workspace.document
        with patch('koei_editor.shared.configuration_gui.messagebox.askyesno', return_value=False) as ask:
            self.workspace.path.set(str(self.folder / 'other' / backend.FORMAT_FILENAME))
            self.assertEqual(ask.call_count, 1)
            self.assertEqual(self.workspace.path.get(), str(document.path))
            self.workspace.game.set(self.workspace._game_labels['arland_totori_dx'])
            self.workspace._selection_changed()
            self.assertEqual(ask.call_count, 2)
        self.assertEqual(self.workspace.selected_game_id, 'arland_rorona_dx')
        self.assertIs(self.workspace.document, document)
        self.assertEqual(self.workspace.staged, {'fullscreen': 1})

    def test_cancelled_reopen_or_browse_does_not_read_or_discard_pending_changes(self):
        self.stage_fullscreen()
        document = self.workspace.document
        with patch('koei_editor.shared.configuration_gui.messagebox.askyesno', return_value=False) as ask, \
                patch.object(backend, 'inspect_config', side_effect=AssertionError('Cancelled selection read a file')):
            self.workspace.open_file()
            self.assertEqual(ask.call_count, 1)
            with patch('koei_editor.shared.configuration_gui.filedialog.askopenfilename',
                       return_value=str(self.folder / 'other' / backend.FORMAT_FILENAME)):
                self.workspace.browse()
            self.assertEqual(ask.call_count, 2)
        self.assertIs(self.workspace.document, document)
        self.assertEqual(self.workspace.staged, {'fullscreen': 1})

    def test_mod_format_uses_exact_file_and_comparison_reports_opaque_changes(self):
        self.file = self.folder / backend.MOD_FORMAT_FILENAME
        self.file.write_bytes(MOD_FIXTURE)
        self.open_game_fixture()
        self.assertEqual(self.workspace.document.format_id, backend.MOD_FORMAT_ID)
        self.assertIn('mod_shadow_multiplier', self.workspace._fields)
        self.assertEqual(self.workspace._fields['mod_shadow_multiplier'].choices,
                         ((1, '1'), (2, '2'), (4, '4'), (8, '8')))

        other = self.folder / 'other-title' / backend.MOD_FORMAT_FILENAME
        other.parent.mkdir(exist_ok=True)
        other.write_bytes(MOD_FIXTURE.replace(b'Sharpen=30', b'Sharpen=60')
                          .replace(b'Keep=yes', b'Keep=no'))
        self.workspace.compare_path.set(str(other))
        self.workspace.compare_game.set(self.workspace.game.get())
        self.workspace.compare()
        self.assertEqual(len(self.workspace.differences.get_children()), 1)
        row = self.workspace.differences.item(self.workspace.differences.get_children()[0], 'values')
        self.assertEqual(row[1:], ('30', '60'))
        self.assertIn('Opaque, unrecognized bytes differ', self.workspace.comparison_status.get())

    def test_compatibility_check_and_application_route_are_retained(self):
        self.open_game_fixture()
        self.workspace.target_game.set(self.workspace._game_labels['arland_totori_dx'])
        self.workspace.check_compatibility()
        self.assertIn('Incompatible:', self.workspace.status.get())
        self.workspace.target_game.set(self.workspace.game.get())
        self.workspace.check_compatibility()
        self.assertIn('Compatible:', self.workspace.status.get())
        self.workspace.game.set(self.workspace._game_labels['arland_totori_dx'])
        self.workspace._selection_changed()
        self.assertIsNone(self.workspace.document)
        self.assertEqual(str(self.workspace.save_button['state']), 'disabled')

        app = Application(self.root, persist_preferences=False)
        with patch.object(backend, 'configuration_data_dir', return_value=self._storage):
            opened = app.execute_command('tool:game_configuration')
            self.root.update()
            self.assertIs(opened, app.game_configuration)
            self.assertEqual(opened.frame.winfo_manager(), 'pack')
            self.assertEqual(app.shell_settings.recent[0], 'tool:game_configuration')
            self.assertIn('tool:game_configuration', {entry.id for entry in app.command_entries()})
            app.language_choice.set('Deutsch')
            app.change_language()
            menu_index = app._editing_tools_menu_index('game_configuration')
            self.assertIsNotNone(menu_index)
            self.assertEqual(app.editing_tools_menu.entrycget(menu_index, 'label'), 'Spielkonfigurationsverwaltung')
            app.language_choice.set('English')
            app.change_language()
            app.show_library()
            app.execute_command('tool:game_configuration')
            self.assertIs(app.game_configuration, opened)
            app.apply_theme('Dark')
            app.apply_theme('Light')


if __name__ == '__main__':
    unittest.main()
