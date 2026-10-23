"""Real Tk lifecycle checks for the retained Manager's Nexus result polling."""
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
import zipfile
from unittest.mock import Mock, patch

from koei_editor.application import Application
from koei_editor.shared.mod_manager import GAME_EXE, LOADER_FILE, ModManager, ModRecord, SafetyError
from koei_editor.shared.mod_manager_gui import ModManagerWorkspace


class ModManagerGuiLifecycleTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.withdraw()
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.manager = ModManager(Path(self.temporary.name) / 'manager')
        self.workspace = ModManagerWorkspace(self.root, self.root, manager=self.manager)
        self.addCleanup(self._destroy_root)

    def _destroy_root(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _pending_manager_polls(self):
        # Tcl retains after scripts even when their registered widget command
        # has been destroyed; inspect the interpreter's actual pending work.
        return tuple(identifier for identifier in self.root.tk.call('after', 'info')
                     if '_poll_nexus_download_results' in str(self.root.tk.call('after', 'info', identifier)))

    def test_frame_destruction_cancels_poll_and_ignores_late_result_callback(self):
        self.assertEqual(len(self._pending_manager_polls()), 1)
        with patch.object(self.manager, 'poll_nexus_download_results') as poll:
            self.workspace.frame.destroy()
            self.assertEqual(self._pending_manager_polls(), ())
            self.workspace._poll_nexus_download_results()
            poll.assert_not_called()
            self.assertEqual(self._pending_manager_polls(), ())

    def test_root_destruction_leaves_no_deleted_manager_callback_in_tcl_queue(self):
        self.assertEqual(len(self._pending_manager_polls()), 1)
        self.root.destroy()
        self.assertEqual(self._pending_manager_polls(), ())

    def test_close_is_idempotent_and_does_not_call_manager_worker(self):
        self.workspace._schedule_nexus_download_poll()
        self.assertEqual(len(self._pending_manager_polls()), 1)
        with patch.object(self.manager, 'poll_nexus_download_results') as poll, \
                patch.object(self.manager, 'enqueue_nexus_download') as enqueue:
            self.workspace.close()
            self.workspace.close()
            self.workspace._schedule_nexus_download_poll()
            self.workspace._poll_nexus_download_results()
            self.assertFalse(self.workspace.enqueue_nexus_download(object(), object()))
            poll.assert_not_called()
            enqueue.assert_not_called()
            self.assertEqual(self._pending_manager_polls(), ())

    def test_application_close_preserves_dirty_veto_then_cancels_poll_on_accept(self):
        app = object.__new__(Application)
        app.root = self.root
        editor = Mock()
        editor.dirty_ok.return_value = False
        app.sessions = {'synthetic': (None, editor)}
        app._tool_workspaces = lambda: (self.workspace,)
        app.close()
        self.assertTrue(self.workspace.frame.winfo_exists())
        self.assertEqual(len(self._pending_manager_polls()), 1)
        editor.dirty_ok.return_value = True
        app.close()
        self.assertEqual(self._pending_manager_polls(), ())

    def test_real_imported_mod_selection_survives_failed_then_successful_recovery_refresh(self):
        folder = Path(self.temporary.name)
        game = folder / 'game'
        game.mkdir()
        (game / GAME_EXE).write_bytes(b'synthetic executable; never run')
        (game / LOADER_FILE).write_bytes(b'synthetic loader; never run')
        self.manager.set_game_root(game)
        archive = folder / 'real-service-fixture.zip'
        with zipfile.ZipFile(archive, 'w') as package:
            package.writestr('OwnedMod/mod.ini', '[Mod]\nName=Fixture\n')
            package.writestr('OwnedMod/assets/model.fmt', b'synthetic replacement')
        record = self.manager.import_archive(archive)
        self.assertIsInstance(record, ModRecord)
        self.assertTrue(self.workspace.refresh())
        self.workspace.mod_table.selection_set(record.id)
        self.workspace._update_controls()
        self.assertEqual(str(self.workspace.remove_button.cget('state')), 'normal')

        with patch.object(self.manager, 'recover_pending_transaction', side_effect=SafetyError('recovery blocked')), \
                patch.object(self.workspace, '_error'):
            self.assertIsNone(self.workspace.refresh())
        self.assertTrue(self.workspace._recovery_blocked)
        self.assertEqual(str(self.workspace.remove_button.cget('state')), 'disabled')
        self.assertEqual(self.workspace.mod_table.selection(), (record.id,))

        self.assertTrue(self.workspace.refresh())
        self.assertFalse(self.workspace._recovery_blocked)
        self.assertEqual(self.workspace.mod_table.selection(), (record.id,))
        self.assertEqual(str(self.workspace.remove_button.cget('state')), 'normal')
        self.assertEqual(self.manager.mods(), (record,))
        self.assertEqual((game / GAME_EXE).read_bytes(), b'synthetic executable; never run')
        self.assertEqual((game / LOADER_FILE).read_bytes(), b'synthetic loader; never run')
