"""Game Hub actions, local annotations, and Tk workspace integration."""
from pathlib import Path
import json
from dataclasses import replace
import tempfile
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.application import Application
from koei_editor.shared import game_hub, game_hub_reports
from koei_editor.shared.game_hub_gui import GameHubWorkspace
from koei_editor.shared.save_discovery import DiscoveryResult, InstalledGame


class GameHubServiceTests(unittest.TestCase):
    def test_tracker_timestamp_string_is_formatted_as_utc(self):
        self.assertEqual(GameHubWorkspace._updated('1700000000'), '2023-11-14 22:13')
        self.assertEqual(GameHubWorkspace._updated('not-a-timestamp'), 'Unknown')

    def test_steam_launch_only_accepts_reviewed_app_ids(self):
        self.assertEqual(game_hub.steam_launch_uri('527270'), 'steam://rungameid/527270')
        with patch('koei_editor.shared.game_hub.webbrowser.open', return_value=True) as opener:
            self.assertTrue(game_hub.launch_via_steam('527270'))
        opener.assert_called_once_with('steam://rungameid/527270', new=0, autoraise=True)
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
        self.folder = Path(temporary.name).resolve()
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
                           last_updated='1700000000', size_on_disk=2_500_000_000),),
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
            self.assertEqual(str(hub.launch_button['state']), 'disabled')
            self.assertEqual(str(hub.folder_button['state']), 'disabled')
            self.assertEqual(str(hub.note_button['state']), 'disabled')
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
        with patch.object(GameHubWorkspace, 'on_show'):
            hub = self.app.show_game_hub()
        hub.query.set('Sophie')
        self.root.update()
        self.root.focus_force()
        self.root.event_generate('<Control-f>')
        self.root.update()

        self.assertEqual(str(self.root.focus_get()), str(hub.search_entry))
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

    def test_numeric_sorting_controls_keep_unknowns_last_and_preserve_selection(self):
        hub = GameHubWorkspace(self.root, self.app.workspace,
                               preferences_path=self.folder / 'preferences.json')
        first = InstalledGame('atelier_sophie', '527270', self.folder / 'first',
                              build_id='10', last_updated='1700000000', size_on_disk=2000)
        second = replace(first, install_path=self.folder / 'second', build_id='2',
                         last_updated='1600000000', size_on_disk=900)
        third = replace(first, install_path=self.folder / 'unknown', build_id=None,
                        last_updated=None, size_on_disk=None)
        hub._result = DiscoveryResult((first, second, third), (), (), 'complete', 1, 10, ())
        hub._installed = {'527270': [first, second, third]}
        hub.status_filter.set('Installed')
        hub.table.selection_set('527270:1')
        hub.sort_by('build')
        self.assertEqual(hub.table.get_children(), ('527270:1', '527270:0', '527270:2'))
        self.assertEqual(hub.table.selection(), ('527270:1',))
        hub.sort_button.invoke()
        self.assertEqual(hub.table.get_children(), ('527270:0', '527270:1', '527270:2'))
        hub.sort_selector.set('Install size')
        self.assertEqual(hub.table.get_children(), ('527270:1', '527270:0', '527270:2'))
        self.assertEqual(hub._result.installed_games, (first, second, third))
        self.assertIn('3/21 rows', hub.result_summary.get())
        hub.query.set('no matching profile')
        self.assertEqual(hub.table.get_children(), ())
        self.assertIn('0/21 rows', hub.result_summary.get())

    def test_export_reports_visible_snapshot_without_paths_notes_or_query_text(self):
        hub = GameHubWorkspace(self.root, self.app.workspace,
                               preferences_path=self.folder / 'preferences.json')
        installed = InstalledGame('atelier_sophie', '527270', self.folder / 'SYNTHETIC_PRIVATE_INSTALL',
                                  build_id='42', last_updated='1700000000', size_on_disk=900)
        hub._result = DiscoveryResult((installed,), (), ('SYNTHETIC_PRIVATE_ISSUE',),
                                      'cancelled', 1, 10, ())
        hub._installed = {'527270': [installed]}
        hub._local_notes = {'527270': 'SYNTHETIC_PRIVATE_NOTE'}
        hub.query.set('SYNTHETIC_PRIVATE_NOTE')
        self.assertEqual(hub.table.get_children(), ('527270:0',))
        destination = self.folder / 'inventory.json'
        with patch('koei_editor.shared.game_hub_gui.filedialog.asksaveasfilename', return_value=str(destination)), \
                patch('koei_editor.shared.game_hub_gui.messagebox.showinfo'), \
                patch('koei_editor.shared.game_hub_gui.messagebox.showerror') as error:
            hub.export_button.invoke()
            error.assert_not_called()
        raw = destination.read_text(encoding='utf-8')
        self.assertNotIn('SYNTHETIC_PRIVATE', raw)
        self.assertNotIn(str(self.folder), raw)
        report = json.loads(raw)
        self.assertEqual(report['scope'], 'visible_rows')
        self.assertEqual(report['coverage']['visible_row_count'], 1)
        self.assertEqual(report['scan']['state'], 'partial')
        self.assertIn('Partial scan', hub.result_summary.get())
        with patch('koei_editor.shared.game_hub_gui.filedialog.asksaveasfilename', return_value=str(destination)), \
                patch('koei_editor.shared.game_hub_gui.messagebox.showerror') as error:
            hub.export_button.invoke()
        error.assert_called_once()
        self.assertEqual(destination.read_text(encoding='utf-8'), raw)

    def test_unscanned_and_failed_refresh_export_states_are_explicit(self):
        hub = GameHubWorkspace(self.root, self.app.workspace,
                               preferences_path=self.folder / 'preferences.json')
        self.assertIn('Not scanned', hub.result_summary.get())
        installed = InstalledGame('atelier_sophie', '527270', self.folder / 'example', build_id='42')
        hub._result = DiscoveryResult((installed,), (), (), 'complete', 1, 10, ())
        hub._installed = {'527270': [installed]}
        hub.render()
        hub.busy = True
        hub._results.put((False, None))
        with patch('koei_editor.shared.game_hub_gui.messagebox.showerror'):
            hub._poll()
        self.assertIn('Refresh failed', hub.result_summary.get())
        destination = self.folder / 'previous.json'
        with patch('koei_editor.shared.game_hub_gui.filedialog.asksaveasfilename', return_value=str(destination)), \
                patch('koei_editor.shared.game_hub_gui.messagebox.showinfo'):
            hub.export_button.invoke()
        report = json.loads(destination.read_bytes())
        self.assertTrue(report['scan']['previous_results'])
        self.assertTrue(report['scan']['refresh_failed'])
        self.assertEqual(hub.table.set('527270:0', 'build'), '42')

    def test_export_cancel_and_busy_state_do_not_write_or_launch(self):
        hub = GameHubWorkspace(self.root, self.app.workspace,
                               preferences_path=self.folder / 'preferences.json')
        with patch('koei_editor.shared.game_hub_gui.filedialog.asksaveasfilename', return_value=''), \
                patch('koei_editor.shared.game_hub_gui.game_hub_reports.write_report_bytes') as export:
            hub.export_visible()
        export.assert_not_called()
        hub.busy = True
        hub._set_busy(True)
        self.assertEqual(str(hub.export_button['state']), 'disabled')
        self.assertEqual(str(hub.sort_selector['state']), 'disabled')
        with patch('koei_editor.shared.game_hub_gui.filedialog.asksaveasfilename') as dialog:
            hub.export_visible()
        dialog.assert_not_called()

    def test_actions_sort_and_details_remain_reachable_in_compact_large_text(self):
        with patch.object(GameHubWorkspace, 'on_show'):
            hub = self.app.show_game_hub()
        for size in ('100%', '140%'):
            self.app.text_size_choice.set(size)
            self.app.change_text_size()
            for width, height in ((980, 760), (780, 680)):
                with self.subTest(size=size, viewport=(width, height)):
                    self.root.geometry(f'{width}x{height}')
                    self.root.update()
                    self.root.update()
                    for widget in (*hub.action_buttons, hub.sort_selector, hub.details_button):
                        self.assertTrue(widget.winfo_ismapped())
                        self.assertGreater(widget.winfo_height(), 1)
                        self.assertGreaterEqual(widget.winfo_width(), widget.winfo_reqwidth())
                        self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                             self.root.winfo_rootx() + self.root.winfo_width())
                        self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                             self.root.winfo_rooty() + self.root.winfo_height())
                    if hub.detail_frame.winfo_manager():
                        self.assertLessEqual(hub.detail_frame.winfo_rooty() + hub.detail_frame.winfo_height(),
                                             hub.actions_frame.winfo_rooty())
                    first = hub.table.bbox(hub.table.get_children()[0])
                    self.assertTrue(first)
                    self.assertLessEqual(first[1] + first[3], hub.table.winfo_height())
        popup = hub.show_details()
        self.assertTrue(popup.winfo_exists())
        popup.destroy()

    def test_export_freezes_visible_bytes_before_modal_callbacks_change_view(self):
        hub = GameHubWorkspace(self.root, self.app.workspace,
                               preferences_path=self.folder / 'preferences.json')
        hub.query.set('Sophie')
        before_ids = tuple(hub.table.get_children())
        before = game_hub_reports.inventory_bytes(None, before_ids)
        destination = self.folder / 'frozen.json'

        def change_view():
            hub.query.set('no matching game')
            hub._refresh_failed = True
            return str(destination)

        with patch('koei_editor.shared.game_hub_gui.filedialog.asksaveasfilename',
                   side_effect=lambda **_kwargs: change_view()), \
                patch('koei_editor.shared.game_hub_gui.messagebox.showinfo'):
            hub.export_visible()
        self.assertEqual(destination.read_bytes(), before)
        self.assertFalse(hub._exporting)

    def test_export_stops_when_modal_dialog_destroys_panel_or_root(self):
        for close_root, raise_error in ((False, False), (True, False), (True, True)):
            with self.subTest(close_root=close_root, raises=raise_error):
                root = tk.Tk()
                hub = GameHubWorkspace(root, root, preferences_path=self.folder / 'other.json')
                destination = self.folder / f'closed-{close_root}-{raise_error}.json'

                def close_during_dialog(**_kwargs):
                    (root if close_root else hub.frame).destroy()
                    if raise_error:
                        raise tk.TclError('synthetic native dialog lost its application')
                    return str(destination)

                with patch('koei_editor.shared.game_hub_gui.filedialog.asksaveasfilename',
                           side_effect=close_during_dialog), \
                        patch('koei_editor.shared.game_hub_gui.messagebox.showinfo') as info, \
                        patch('koei_editor.shared.game_hub_gui.messagebox.showerror') as error:
                    hub.export_visible()
                self.assertFalse(destination.exists())
                self.assertFalse(hub._exporting)
                info.assert_not_called()
                error.assert_not_called()
                if not close_root:
                    root.destroy()


if __name__ == '__main__':
    unittest.main()
