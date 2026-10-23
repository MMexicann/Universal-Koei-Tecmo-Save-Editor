"""Real Tk save-management workflows, worker isolation and safe lifecycle."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from koei_editor.application import Application
from koei_editor.shared.save_management_gui import SaveManagementWindow
from koei_editor.shared.save_vault import SaveVault
from tests.test_wo1_pc_format import procedural_raw
from tests.owned_directory_contract import install_owned_directory_contract


class SaveManagementProfileVaultBindingTests(unittest.TestCase):
    class VaultPath:
        def __init__(self, value):
            self.value = value
            self.trace = None

        def get(self):
            return self.value

        def set(self, value):
            self.value = value
            if self.trace is not None:
                self.trace()

    @staticmethod
    def manager_with_profile(profile_window):
        manager = SimpleNamespace(
            busy=False,
            _closed=False,
            _reverting_vault_path=False,
            profile_window=profile_window,
            history=Mock(),
            vault_output=Mock(),
            _set_output=Mock(),
            status=Mock(),
            window=object(),
            _palette={'background': '#fff', 'text': '#000'},
            _start=Mock(),
            _history_result=Mock(),
        )
        manager._profile_operation_busy = lambda: SaveManagementWindow._profile_operation_busy(manager)
        manager._invoke = lambda prepare: prepare()
        manager.history.get_children.return_value = ()
        manager.history.selection.return_value = ()
        manager.vault_path = SaveManagementProfileVaultBindingTests.VaultPath(
            profile_window.vault_path if profile_window is not None else '')
        manager.vault_path.trace = lambda: SaveManagementWindow._vault_changed(manager)
        return manager

    def test_vault_change_closes_old_profile_window_and_reopens_with_new_vault(self):
        old_profile = SimpleNamespace(vault_path='/old-vault', busy=False, _closed=False)
        old_profile.close = Mock(side_effect=lambda: setattr(old_profile, '_closed', True))
        manager = self.manager_with_profile(old_profile)
        manager.vault_path.value = '/new-vault'
        new_profile = SimpleNamespace(vault_path='/new-vault', _closed=False)

        with patch('koei_editor.shared.save_management_gui.messagebox.showinfo'), \
                patch('koei_editor.shared.save_management_gui.SaveManagementWindow._set_output'), \
                patch('koei_editor.shared.playthrough_profiles_gui.PlaythroughProfilesWindow',
                      return_value=new_profile) as create_window:
            SaveManagementWindow._vault_changed(manager)
            self.assertIsNone(manager.profile_window)
            SaveManagementWindow.open_playthrough_profiles(manager)

        old_profile.close.assert_called_once_with()
        create_window.assert_called_once_with(
            manager.window, vault_path='/new-vault', selected_snapshot_id=None,
            palette=manager._palette,
        )
        self.assertIs(manager.profile_window, new_profile)

    def test_vault_change_is_reverted_while_profile_worker_is_busy(self):
        profile = SimpleNamespace(vault_path='/old-vault', busy=True, _closed=False)
        profile.close = Mock()
        manager = self.manager_with_profile(profile)
        manager.vault_path.value = '/new-vault'

        with patch('koei_editor.shared.save_management_gui.messagebox.showinfo') as showinfo, \
                patch('koei_editor.shared.save_management_gui.SaveManagementWindow._set_output'):
            SaveManagementWindow._vault_changed(manager)

        self.assertEqual(manager.vault_path.get(), '/old-vault')
        self.assertIs(manager.profile_window, profile)
        profile.close.assert_not_called()
        manager.history.delete.assert_not_called()
        manager._set_output.assert_not_called()
        showinfo.assert_called_once()

    def test_create_and_load_vault_do_not_start_during_profile_operation(self):
        profile = SimpleNamespace(vault_path='/old-vault', busy=True, _closed=False)
        manager = self.manager_with_profile(profile)

        with patch('koei_editor.shared.save_management_gui.filedialog.askdirectory') as choose_directory, \
                patch('koei_editor.shared.save_vault.SaveVault') as save_vault, \
                patch('koei_editor.shared.save_management_gui.messagebox.showinfo') as showinfo:
            SaveManagementWindow.create_vault(manager)
            SaveManagementWindow.load_vault(manager)

        choose_directory.assert_not_called()
        save_vault.assert_not_called()
        save_vault.create.assert_not_called()
        save_vault.list_snapshots.assert_not_called()
        manager._start.assert_not_called()
        manager._history_result.assert_not_called()
        manager.history.delete.assert_not_called()
        manager._set_output.assert_not_called()
        self.assertEqual(showinfo.call_count, 2)

    def test_create_vault_rechecks_path_if_profile_work_starts_during_picker(self):
        profile = SimpleNamespace(vault_path='/old-vault', busy=False, _closed=False)
        manager = self.manager_with_profile(profile)

        def start_profile_work(*_args, **_kwargs):
            profile.busy = True
            return '/new-parent'

        with patch('koei_editor.shared.save_management_gui.filedialog.askdirectory',
                   side_effect=start_profile_work) as choose_directory, \
                patch('koei_editor.shared.save_vault.SaveVault') as save_vault, \
                patch('koei_editor.shared.save_management_gui.messagebox.showinfo') as showinfo:
            SaveManagementWindow.create_vault(manager)

        choose_directory.assert_called_once()
        self.assertEqual(manager.vault_path.get(), '/old-vault')
        save_vault.assert_not_called()
        save_vault.create.assert_not_called()
        save_vault.list_snapshots.assert_not_called()
        manager._start.assert_not_called()
        manager._history_result.assert_not_called()
        manager.history.delete.assert_not_called()
        manager._set_output.assert_not_called()
        showinfo.assert_called_once()


class SaveManagementGuiTests(unittest.TestCase):
    def setUp(self):
        install_owned_directory_contract(self)
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
        self.assertIn(f'Copy 1: {self.source.name}', manager.doctor_output.get('1.0', 'end'))
        report = self.folder / 'report.json'
        with patch('koei_editor.shared.save_management_gui.filedialog.asksaveasfilename', return_value=str(report)):
            manager.export_doctor()
            self.finish(manager)
        self.assertTrue(json.loads(report.read_bytes())[0]['success'])
        original = report.read_bytes()
        self.assertNotIn(self.source.name.encode(), original)
        self.assertNotIn(str(self.folder).encode(), original)
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
        local_report = manager.doctor_output.get('1.0', 'end')
        for index, path in enumerate(manager.paths):
            self.assertIn(f'Copy {index + 1}: {path.name}', local_report)
        exported = self.folder / 'multi-report.json'
        with patch('koei_editor.shared.save_management_gui.filedialog.asksaveasfilename', return_value=str(exported)):
            manager.export_doctor()
            self.finish(manager)
        exported_reports = json.loads(exported.read_bytes())
        self.assertEqual(len(exported_reports), 2)
        self.assertTrue(all(report['success'] for report in exported_reports))
        for private in (self.source.name, second.name, str(self.folder)):
            self.assertNotIn(private.encode(), exported.read_bytes())
        vault_path = self.folder / 'vault'
        SaveVault.create(vault_path)
        manager.vault_path.set(str(vault_path))
        manager.snapshot()
        self.finish(manager)
        ids = manager.history.get_children()
        self.assertEqual(len(ids), 2)
        snapshots = {item.id: item for item in SaveVault(vault_path).list_snapshots()}
        self.assertEqual({manager.history.set(snapshot_id, 'filename') for snapshot_id in ids},
                         {self.source.name, second.name})
        for snapshot_id in ids:
            self.assertEqual(manager.history.set(snapshot_id, 'created_utc'), snapshots[snapshot_id].created_utc)
            self.assertEqual(manager.history.item(snapshot_id, 'text'), snapshot_id)
        self.assertEqual(manager.history.heading('created_utc')['text'], 'Created (UTC)')
        self.assertTrue(manager.history.cget('yscrollcommand'))
        self.assertEqual(str(manager.history_scrollbar.cget('orient')), 'vertical')
        # History browsing must keep its scrollbar visible after the tree's
        # wider filename/date columns are constrained by a smaller window.
        original_snapshots = tuple(snapshots.values())
        preview_rows = tuple(replace(original_snapshots[0], id=f'preview-{index}') for index in range(18))
        manager._history_result(original_snapshots + preview_rows)
        manager.notebook.select(manager.vault_tab)
        for width, height in ((820, 650), (1000, 780)):
            with self.subTest(width=width, height=height):
                manager.window.geometry(f'{width}x{height}')
                self.root.update()
                bar = manager.history_scrollbar
                self.assertTrue(bar.winfo_ismapped())
                self.assertGreaterEqual(bar.winfo_width(), bar.winfo_reqwidth())
                self.assertGreater(bar.winfo_height(), 0)
                self.assertLessEqual(bar.winfo_rootx() + bar.winfo_width(),
                                     manager.window.winfo_rootx() + manager.window.winfo_width())
                self.assertLessEqual(bar.winfo_rooty() + bar.winfo_height(),
                                     manager.window.winfo_rooty() + manager.window.winfo_height())
                self.assertLessEqual(manager.history.winfo_rootx() + manager.history.winfo_width(),
                                     bar.winfo_rootx())
                self.assertLess(manager.history.yview()[1], 1)
                horizontal = manager.history_horizontal_scrollbar
                self.assertTrue(horizontal.winfo_ismapped())
                self.assertGreaterEqual(horizontal.winfo_height(), horizontal.winfo_reqheight())
                self.assertLessEqual(horizontal.winfo_rootx() + horizontal.winfo_width(),
                                     manager.window.winfo_rootx() + manager.window.winfo_width())
                self.assertLessEqual(horizontal.winfo_rooty() + horizontal.winfo_height(),
                                     manager.window.winfo_rooty() + manager.window.winfo_height())
                self.assertLessEqual(manager.history.winfo_rooty() + manager.history.winfo_height(),
                                     horizontal.winfo_rooty())
        manager._history_result(original_snapshots)
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
