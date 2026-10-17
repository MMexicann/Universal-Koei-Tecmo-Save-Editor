"""Real Tk save-management workflows, worker isolation and safe lifecycle."""
import json
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.application import Application
from koei_editor.shared.save_management_gui import SaveManagementWindow
from koei_editor.shared.save_vault import SaveVault
from tests.test_wo1_pc_format import procedural_raw


class SaveManagementGuiTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.copies = self.folder / 'copies'
        self.copies.mkdir()
        self.raw = procedural_raw()
        self.source = self.copies / 'slot.dat'
        self.source.write_bytes(self.raw)
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.destroy)
        self.app = Application(self.root, preferences_path=self.folder / 'prefs.json', persist_preferences=False)
        self.root.update()

    def destroy(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def finish(self, tool):
        deadline = time.monotonic() + 20
        while tool.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(.01)
        self.assertFalse(tool.busy, 'Save-management worker did not finish.')
        self.root.update()

    def tools(self):
        self.app.show_save_library()
        library = self.app.save_library
        library.game.set(next(label for label, value in library._games.items() if value == 'wo1'))
        library.management_button.invoke()
        self.root.update()
        return library.management

    def test_unscanned_entrypoint_doctor_reports_export_theme_and_reopening(self):
        manager = self.tools()
        self.assertIsInstance(manager, SaveManagementWindow)
        manager.copy_path.set(str(self.source))
        manager.diagnose()
        self.finish(manager)
        self.assertTrue(manager.doctor_reports[0].success)
        self.assertIn('byte-for-byte', manager.doctor_output.get('1.0', 'end'))
        self.assertNotIn(self.source.name, manager.doctor_output.get('1.0', 'end'))
        report = self.folder / 'report.json'
        with patch('koei_editor.shared.save_management_gui.filedialog.asksaveasfilename', return_value=str(report)):
            manager.export_doctor()
            self.finish(manager)
        self.assertTrue(json.loads(report.read_bytes())[0]['success'])
        original = report.read_bytes()
        with patch('koei_editor.shared.save_management_gui.filedialog.asksaveasfilename', return_value=str(report)), \
                patch('koei_editor.shared.save_management_gui.messagebox.showerror') as error:
            manager.export_doctor()
            self.finish(manager)
        error.assert_called_once()
        self.assertEqual(report.read_bytes(), original)
        self.app.apply_theme('Dark')
        self.assertNotEqual(manager.doctor_output.cget('background'), '#ffffff')
        manager.close()
        self.assertTrue(manager._closed)
        self.app.save_library.management_button.invoke()
        self.assertIsNot(self.app.save_library.management, manager)
        self.assertFalse(self.app.save_library.management._closed)
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_multiselect_doctor_vault_branch_compare_restore_and_history_refresh(self):
        self.app.show_save_library()
        library = self.app.save_library
        library.game.set(next(label for label, value in library._games.items() if value == 'wo1'))
        library.folder.set(str(self.copies))
        second = self.copies / 'slot2.dat'
        second.write_bytes(self.raw)
        library.scan()
        self.finish(library)
        library.table.selection_set(library.table.get_children())
        library.selection_changed()
        library.manage_selected()
        manager = library.management
        self.assertEqual(len(manager.paths), 2)
        manager.diagnose()
        self.finish(manager)
        self.assertEqual(len(manager.doctor_reports), 2)
        self.assertTrue(all(report.success for report in manager.doctor_reports))
        vault_path = self.folder / 'vault'
        SaveVault.create(vault_path)
        manager.vault_path.set(str(vault_path))
        manager.snapshot()
        self.finish(manager)
        ids = manager.history.get_children()
        self.assertEqual(len(ids), 2)
        manager.history.selection_set(ids)
        manager.compare()
        self.finish(manager)
        self.assertTrue(json.loads(manager.vault_output.get('1.0', 'end'))['identical_gameplay_bytes'])
        manager.history.selection_set(ids[-1])
        manager.snapshot_label.set('Before final battle')
        manager.relabel()
        self.finish(manager)
        self.assertEqual(manager.history.item(ids[-1], 'values')[-1], 'Before final battle')
        manager.branch_name.set('alternate')
        manager.branch()
        self.finish(manager)
        self.assertEqual(SaveVault(vault_path).list_branches()['alternate'], ids[-1])
        with patch('koei_editor.shared.save_management_gui.filedialog.askdirectory', return_value=str(self.folder)):
            manager.restore()
            self.finish(manager)
        restored = self.folder / ('Restored-' + ids[-1])
        restored_files = tuple(restored.glob('*.dat'))
        self.assertEqual(len(restored_files), 1)
        self.assertEqual(restored_files[0].read_bytes(), self.raw)
        with patch('koei_editor.shared.save_management_gui.messagebox.askyesno', return_value=True):
            manager.delete()
            self.finish(manager)
        self.assertFalse(manager.history.exists(ids[-1]))
        self.assertEqual(len(SaveVault(vault_path).list_snapshots()), 1)
        manager.vault_path.set(str(self.folder / 'other-vault'))
        self.assertEqual(manager.history.get_children(), ())
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertEqual(second.read_bytes(), self.raw)

    def test_read_only_discovery_runs_in_worker_and_exposes_local_paths_only_in_ui(self):
        manager = self.tools()
        steam = self.folder / 'Steam'
        steam.mkdir()
        manager.steam_root.set(str(steam))
        thread_ids = []
        from koei_editor.shared import save_discovery
        original = save_discovery.discover_saves
        def capture(*args, **kwargs):
            thread_ids.append(threading.get_ident())
            return original(*args, **kwargs)
        with patch.object(save_discovery, 'discover_saves', side_effect=capture):
            manager.discover()
            self.finish(manager)
        self.assertEqual(len(thread_ids), 1)
        self.assertNotEqual(thread_ids[0], threading.get_ident())
        self.assertIn('complete', manager.discovery_output.get('1.0', 'end'))
        self.assertEqual(list(steam.iterdir()), [])

    def test_application_and_tool_close_wait_for_active_storage_operation(self):
        manager = self.tools()
        manager.copy_path.set(str(self.source))
        vault_path = self.folder / 'vault'
        SaveVault.create(vault_path)
        manager.vault_path.set(str(vault_path))
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        original = SaveVault.snapshot
        def delayed(vault, *args, **kwargs):
            started.set()
            if not release.wait(10):
                raise ValueError('Test operation did not resume.')
            return original(vault, *args, **kwargs)
        with patch.object(SaveVault, 'snapshot', delayed):
            manager.snapshot()
            self.assertTrue(started.wait(5))
            with patch('tkinter.messagebox.showinfo') as notice, patch.object(self.root, 'destroy') as destroy:
                self.app.close()
                manager.close()
            self.assertEqual(notice.call_count, 2)
            destroy.assert_not_called()
            self.assertFalse(manager._closed)
            release.set()
            self.finish(manager)
        self.assertEqual(len(SaveVault(vault_path).list_snapshots()), 1)
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.app.close()
        self.assertTrue(manager._closed)


if __name__ == '__main__':
    unittest.main()
