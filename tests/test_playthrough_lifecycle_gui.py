"""Real nested profile windows remain bound to one Vault during workers."""
import gc
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.application import Application
from koei_editor.shared.save_vault import SaveVault
from tests import test_playthrough_profiles as profile_fixtures


class PlaythroughLifecycleGuiTests(unittest.TestCase):
    def setUp(self):
        self.fixture = profile_fixtures.PlaythroughProfileIntegrationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.app = None
        self.manager = None
        self.addCleanup(self.dispose)
        self.app = Application(
            self.root, preferences_path=self.fixture.root / 'prefs.json',
            persist_preferences=False)
        self.app.show_save_library()
        self.app.save_library.management_button.invoke()
        self.manager = self.app.save_library.management
        self.manager.vault_path.set(str(self.fixture.vault.root))
        self.manager.load_vault()
        self.finish(self.manager)
        self.manager.history.selection_set(self.fixture.snapshot.id)
        self.manager.open_playthrough_profiles()
        self.finish(self.manager.profile_window)
        self.other = SaveVault.create(self.fixture.root / 'other-vault')

    def finish(self, tool):
        deadline = time.monotonic() + 10
        while tool.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(.01)
        self.assertFalse(tool.busy, 'Nested storage worker did not finish.')
        self.root.update()

    def dispose(self):
        if self.manager is not None:
            profile = self.manager.profile_window
            if profile is not None and profile.busy:
                self.finish(profile)
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        self.app = self.manager = self.root = None
        gc.collect()

    def test_idle_vault_change_destroys_old_window_and_reopens_bound_to_new_history(self):
        manager = self.manager
        old = manager.profile_window
        self.assertEqual(old.vault_path, str(self.fixture.vault.root))
        self.assertIn(self.fixture.snapshot.id, old.snapshots)
        manager.vault_path.set(str(self.other.root))
        self.root.update()
        self.assertTrue(old._closed)
        self.assertFalse(old.window.winfo_exists())
        self.assertIsNone(manager.profile_window)
        self.assertEqual(manager.history.get_children(), ())
        manager.open_playthrough_profiles()
        new = manager.profile_window
        self.finish(new)
        self.assertIsNot(new, old)
        self.assertEqual(new.vault_path, str(self.other.root))
        self.assertEqual(new.snapshots, {})
        self.assertEqual(new.profiles, {})
        self.assertEqual(self.fixture.source.read_bytes(), self.fixture.raw)

    def test_busy_profile_blocks_real_vault_trace_parent_close_and_application_quit(self):
        manager = self.manager
        profile = manager.profile_window
        history = manager.history.get_children()
        release = threading.Event()
        try:
            profile._start(lambda: release.wait(10), lambda result: None)
            with patch('tkinter.messagebox.showinfo') as notice, \
                    patch('koei_editor.shared.save_management_gui.filedialog.askdirectory') as choose:
                manager.vault_path.set(str(self.other.root))
                self.assertEqual(manager.vault_path.get(), str(self.fixture.vault.root))
                self.assertEqual(manager.history.get_children(), history)
                self.assertIs(manager.profile_window, profile)
                manager.create_vault()
                manager.load_vault()
                choose.assert_not_called()
                self.assertFalse(manager.busy)
                profile.close()
                manager.close()
                with patch.object(self.root, 'destroy', wraps=self.root.destroy) as destroy:
                    self.app.close()
                destroy.assert_not_called()
                self.assertFalse(profile._closed)
                self.assertFalse(manager._closed)
                self.assertTrue(self.root.winfo_exists())
                self.assertTrue(profile.window.winfo_exists())
                self.assertEqual(notice.call_count, 6)
        finally:
            release.set()
            self.finish(profile)
        self.assertEqual(self.fixture.source.read_bytes(), self.fixture.raw)
        with patch.object(self.root, 'destroy', wraps=self.root.destroy) as destroy:
            self.app.close()
        destroy.assert_called_once_with()
        self.assertTrue(profile._closed)
        self.assertTrue(manager._closed)

    def test_picker_reentrancy_rechecks_real_trace_without_creating_second_vault(self):
        manager = self.manager
        profile = manager.profile_window
        release = threading.Event()
        new_parent = self.fixture.root / 'new-parent'
        new_parent.mkdir()

        def start_profile_worker(**kwargs):
            profile._start(lambda: release.wait(10), lambda result: None)
            return str(new_parent)

        try:
            with patch('koei_editor.shared.save_management_gui.filedialog.askdirectory',
                       side_effect=start_profile_worker), \
                    patch('tkinter.messagebox.showinfo') as notice:
                manager.create_vault()
            notice.assert_called_once()
            self.assertFalse((new_parent / 'SaveVault').exists())
            self.assertEqual(manager.vault_path.get(), str(self.fixture.vault.root))
            self.assertIs(manager.profile_window, profile)
            self.assertFalse(manager.busy)
        finally:
            release.set()
            self.finish(profile)


if __name__ == '__main__':
    unittest.main()
