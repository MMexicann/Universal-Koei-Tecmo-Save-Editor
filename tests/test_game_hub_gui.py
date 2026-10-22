"""Game Hub actions, local annotations, and Tk workspace integration."""
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.application import Application
from koei_editor.shared import game_hub
from koei_editor.shared.game_hub_gui import GameHubWorkspace
from koei_editor.shared.save_discovery import DiscoveryResult, InstalledGame


class GameHubServiceTests(unittest.TestCase):
    def test_tracker_timestamp_string_is_formatted_as_utc(self):
        self.assertEqual(GameHubWorkspace._updated('1700000000'), '2023-11-14 22:13')
        self.assertEqual(GameHubWorkspace._updated('not-a-timestamp'), 'Unknown')

    def test_steam_launch_only_accepts_reviewed_app_ids(self):
        self.assertEqual(game_hub.steam_launch_uri('527270'), 'steam://run/527270')
        with patch('koei_editor.shared.game_hub.webbrowser.open', return_value=True) as opener:
            self.assertTrue(game_hub.launch_via_steam('527270'))
        opener.assert_called_once_with('steam://run/527270', new=0, autoraise=True)
        for value in ('527271', '0527270', '1;open', 527270, ''):
            with self.subTest(value=value), self.assertRaises(ValueError):
                game_hub.steam_launch_uri(value)

    def test_notes_are_bounded_persisted_local_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            settings = game_hub.GameHubNotes(Path(temporary) / 'hub.json')
            self.assertEqual(settings.set_note('527270', '  Verify backup location  '),
                             'Verify backup location')
            self.assertEqual(game_hub.GameHubNotes(settings.path).load(),
                             {'527270': 'Verify backup location'})
            raw = settings.path.read_text(encoding='utf-8')
            self.assertNotIn(temporary, raw)
            self.assertEqual(settings.set_note('527270', ''), '')
            self.assertEqual(settings.load(), {})
            with self.assertRaises(ValueError):
                settings.set_note('unknown', 'note')
            with self.assertRaises(ValueError):
                settings.set_note('527270', 'n' * (game_hub.MAX_NOTE_LENGTH + 1))


class GameHubGuiTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.destroy)
        self.app = Application(self.root, preferences_path=self.folder / 'preferences.json',
                               persist_preferences=False)
        self.root.update()

    def destroy(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def finish(self, workspace):
        deadline = time.monotonic() + 10
        while workspace.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(.01)
        self.root.update()
        self.assertFalse(workspace.busy, 'Game Hub discovery worker did not finish.')

    def test_navigation_scans_off_tk_thread_and_exposes_install_actions(self):
        install = self.folder / 'Steam' / 'steamapps' / 'common' / 'Atelier Sophie'
        library = self.folder / 'Steam'
        install.mkdir(parents=True)
        library.mkdir(exist_ok=True)
        result = DiscoveryResult(
            (InstalledGame('atelier_sophie', '527270', install,
                           library_path=library, build_id='123456',
                           last_updated=1_700_000_000, size_on_disk=2_500_000_000),),
            (), (), 'complete', 0, 0, ('atelier_sophie',))
        thread_ids, calls = [], []

        def discover(**kwargs):
            thread_ids.append(threading.get_ident())
            calls.append(kwargs)
            return result

        with patch('koei_editor.shared.save_discovery.discover_installed_builds', side_effect=discover):
            hub = self.app.show_game_hub()
            self.assertIsInstance(hub, GameHubWorkspace)
            self.assertEqual(hub.frame.winfo_manager(), 'pack')
            self.finish(hub)

        self.assertNotEqual(thread_ids[0], threading.get_ident())
        self.assertIn('cancel', calls[0])
        self.assertEqual(hub.status_filter.get(), 'All tracked games')
        self.assertEqual(hub.table.set('527270:0', 'status'), 'Installed')
        self.assertEqual(hub.table.set('527270:0', 'build'), '123456')
        hub.table.selection_set('527270:0')
        hub.selection_changed()
        details = hub.details.get('1.0', 'end')
        self.assertIn(str(install), details)
        self.assertIn('Steam build ID: 123456', details)
        self.assertIn('not an in-game patch number', details)

        with patch('koei_editor.shared.game_hub.launch_via_steam', return_value=True) as launch, \
                patch('koei_editor.shared.game_hub.open_install_folder', return_value=True) as show_folder:
            hub.busy = True
            hub._set_busy(True)
            self.assertEqual(hub.launch_button['state'], 'disabled')
            self.assertEqual(hub.folder_button['state'], 'disabled')
            self.assertEqual(hub.note_button['state'], 'disabled')
            hub.busy = False
            hub._set_busy(False)
            hub.launch_button.invoke()
            hub.folder_button.invoke()
        launch.assert_called_once_with('527270')
        show_folder.assert_called_once_with(install)

        with patch('koei_editor.shared.game_hub_gui.simpledialog.askstring', return_value='Keep two copies'):
            hub.note_button.invoke()
        self.assertEqual(hub.table.set('527270:0', 'notes'), 'Keep two copies')
        self.assertEqual(hub.notes.load(), {'527270': 'Keep two copies'})
        self.assertIn('tool:game_hub', {entry.id for entry in self.app.command_entries()})

    def test_partial_scan_does_not_claim_unlisted_games_are_uninstalled(self):
        self.app.game_hub = GameHubWorkspace(self.root, self.app.workspace,
                                             preferences_path=self.folder / 'preferences.json')
        hub = self.app.game_hub
        hub._result = DiscoveryResult((), (), (), 'entry_limit', 2000, 10, ())
        hub.render()
        row = '527270:missing'
        self.assertEqual(hub.table.set(row, 'status'), 'Not detected (partial scan)')

    def test_control_f_focuses_and_selects_game_hub_search(self):
        hub = GameHubWorkspace(self.root, self.app.workspace,
                               preferences_path=self.folder / 'preferences.json')
        self.app.game_hub = hub
        hub.frame.pack(fill='both', expand=True)
        self.root.update()
        self.root.focus_force()
        self.root.event_generate('<Control-f>')
        self.root.update()

        self.assertIs(self.root.focus_get(), hub.search_entry)
        self.assertTrue(hub.search_entry.selection_present())

    def test_refresh_failure_preserves_prior_installations(self):
        install = self.folder / 'Steam' / 'steamapps' / 'common' / 'Atelier Sophie'
        install.mkdir(parents=True)
        result = DiscoveryResult(
            (InstalledGame('atelier_sophie', '527270', install,
                           build_id='123456', last_updated='1700000000'),),
            (), (), 'complete', 1, 10, ('atelier_sophie',))
        hub = GameHubWorkspace(self.root, self.app.workspace,
                               preferences_path=self.folder / 'preferences.json')
        hub._result = result
        hub._installed = {'527270': list(result.installed_games)}
        hub.render()
        hub.busy = True
        hub._results.put((False, None))

        with patch('koei_editor.shared.game_hub_gui.messagebox.showerror'):
            hub._poll()

        self.assertIs(hub._result, result)
        self.assertEqual(hub.table.set('527270:0', 'status'), 'Installed')
        self.assertIn('refresh failed', hub.status.get().casefold())

    def test_cancelled_scan_does_not_report_a_limit(self):
        hub = GameHubWorkspace(self.root, self.app.workspace,
                               preferences_path=self.folder / 'preferences.json')
        hub.busy = True
        hub._results.put((True, DiscoveryResult((), (), (), 'cancelled', 25, 10, ())))

        hub._poll()

        self.assertIn('Scan cancelled', hub.status.get())
        self.assertNotIn('cancelled limit', hub.status.get())


if __name__ == '__main__':
    unittest.main()
