"""Real profile-window callbacks preserve sources and prepare isolated copies."""
import gc
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.shared.playthrough_profiles import dump_component_snapshot
from koei_editor.shared.playthrough_profiles_gui import PlaythroughProfilesWindow
from tests import test_playthrough_profiles as profile_fixtures


class PlaythroughProfilesGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.dispose_window)
        self.fixture = profile_fixtures.PlaythroughProfileIntegrationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root.withdraw()
        self.window = PlaythroughProfilesWindow(
            self.root, vault_path=self.fixture.vault.root,
            selected_snapshot_id=self.fixture.snapshot.id)
        self.finish_operation()

    def dispose_window(self):
        if getattr(self, 'window', None) is not None and not self.window._closed:
            self.finish_operation()
            self.window.close()
        self.root.destroy()
        self.window = None
        self.root = None
        # Collect dead Tk cycles on the Tk thread before another worker starts.
        gc.collect()

    def finish_operation(self):
        deadline = time.monotonic() + 10
        while self.window.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertFalse(self.window.busy, 'The profile operation did not finish.')
        self.root.update()

    def select_profile(self, profile_id):
        self.window.profile_tree.selection_set(profile_id)
        self.root.update()

    def test_create_preview_and_prepare_restore_only_to_a_new_environment(self):
        self.assertIn(self.fixture.snapshot.id, self.window.snapshots)
        component_file = self.fixture.root / 'manager-component.json'
        component_file.write_text(
            dump_component_snapshot(self.fixture.components()[0]), encoding='utf-8')
        self.window.profile_name.set('GUI reviewed profile')
        self.window.profile_game_version.set('1.02')
        self.window.component_paths['mod_configuration'].set(str(component_file))
        self.window.create_profile()
        self.finish_operation()
        self.assertEqual(len(self.window.profiles), 1)
        profile_id = next(iter(self.window.profiles))
        self.select_profile(profile_id)
        self.window.installed_game_version.set('1.02')
        self.window.preview_profile()
        self.finish_operation()
        self.assertTrue(self.window.current_report['compatible'])
        self.assertFalse(self.window.current_report['components_applied'])

        parent = self.fixture.root / 'environments'
        parent.mkdir()
        self.window.destination_parent.set(str(parent))
        with patch('koei_editor.shared.playthrough_profiles_gui.messagebox.askyesno', return_value=True), \
                patch('koei_editor.shared.playthrough_profiles_gui.messagebox.showinfo'), \
                patch('koei_editor.shared.playthrough_profiles_gui.messagebox.showerror') as errors:
            self.window.prepare_environment()
            self.finish_operation()
        errors.assert_not_called()
        report = self.window.current_report
        output = parent / ('Playthrough-' + profile_id[:8])
        self.assertEqual((output / report['restored_save_path']).read_bytes(), self.fixture.raw)
        self.assertEqual((output / 'save-copy' / 'PARAM.SFO').read_bytes(), self.fixture.context)
        self.assertTrue((output / 'components' / 'mod_configuration.json').is_file())
        self.assertTrue((output / 'playthrough-report.json').is_file())
        self.assertFalse(report['components_applied'])
        self.assertFalse(report['live_save_written'])
        self.assertEqual(self.fixture.source.read_bytes(), self.fixture.raw)
        self.assertEqual((self.fixture.source.parent / 'PARAM.SFO').read_bytes(), self.fixture.context)

    def test_changed_version_requires_new_preview_and_busy_storage_blocks_close(self):
        profile = self.fixture.make_profile(components=())
        self.window._refresh()
        self.finish_operation()
        self.select_profile(profile.id)
        self.window.installed_game_version.set('1.02')
        self.window.preview_profile()
        self.finish_operation()
        self.window.installed_game_version.set('1.03')
        parent = self.fixture.root / 'other-environments'
        parent.mkdir()
        self.window.destination_parent.set(str(parent))
        with patch('koei_editor.shared.playthrough_profiles_gui.messagebox.showerror') as error, \
                patch('koei_editor.shared.playthrough_profiles_gui.messagebox.askyesno') as confirmation:
            self.window.prepare_environment()
        error.assert_called_once()
        confirmation.assert_not_called()
        self.assertEqual(tuple(parent.iterdir()), ())

        release = threading.Event()
        try:
            self.window._start(lambda: release.wait(5), lambda result: None)
            with patch('koei_editor.shared.playthrough_profiles_gui.messagebox.showinfo') as notice:
                self.window.close()
            notice.assert_called_once()
            self.assertFalse(self.window._closed)
            self.assertTrue(self.window.window.winfo_exists())
        finally:
            release.set()
            self.finish_operation()
        self.window.close()
        self.assertTrue(self.window._closed)


if __name__ == '__main__':
    unittest.main()
