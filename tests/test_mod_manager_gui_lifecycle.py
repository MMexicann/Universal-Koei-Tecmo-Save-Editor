"""Real Tk lifecycle checks for the retained Manager's Nexus result polling."""
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
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
        folder = Path(self.temporary.name).resolve()
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

    def test_game_selector_isolates_libraries_and_restores_each_game_context(self):
        from tests.test_mod_manager import install_root, make_archive
        from tests.test_mod_manager_multigame import nioh3_root, package
        folder = Path(self.temporary.name).resolve()
        nioh2 = install_root(folder / 'nioh2')
        self.manager.set_game_root(nioh2)
        original = self.manager.import_archive(make_archive(folder / 'nioh2.zip', mod_id='same-id'))
        self.workspace.refresh()
        self.workspace.loader_confirmed.set(True)
        self.assertTrue(self.workspace.select_game('nioh3_pc'))
        self.assertFalse(self.workspace.loader_confirmed.get())
        self.assertEqual(self.workspace.manager.mods(), ())
        self.assertIsNone(self.workspace.manager.current_game_root)
        nioh3 = nioh3_root(folder / 'nioh3')
        self.workspace.manager.set_game_root(nioh3)
        self.workspace.manager.import_archive(package(folder / 'nioh3.zip', mod_id='same-id'))
        self.workspace.refresh()
        self.assertIn('library copy is retained', self.workspace.capability_text.get())
        self.assertTrue(self.workspace.select_game('nioh2_pc'))
        self.assertIs(self.workspace.manager, self.manager)
        self.assertEqual(self.workspace.manager.current_game_root, nioh2)
        self.assertEqual(self.workspace.manager.mods(), (original,))
        self.assertTrue(self.workspace.select_game('nioh3_pc'))
        self.assertEqual(self.workspace.manager.current_game_root, nioh3)
        self.assertNotEqual(self.workspace.manager.mods()[0].content_sha256, original.content_sha256)

    def test_game_switch_is_blocked_by_unresolved_transaction_and_preserves_selection(self):
        self.workspace._recovery_blocked = True
        with self.assertRaises(ValueError):
            self.workspace.select_game('nioh3_pc')
        self.assertIs(self.workspace.manager, self.manager)
        self.assertEqual(self.workspace.game_choice.get(), self.manager.adapter.title)

    def test_archive_handoff_routes_manifest_to_game_and_imports_without_deployment(self):
        from tests.test_mod_manager_multigame import package
        folder = Path(self.temporary.name).resolve()
        archive = package(folder / 'workshop-export.zip')
        record = self.workspace.import_archive_path(archive)
        self.assertEqual(self.workspace.manager.game_id, 'nioh3_pc')
        self.assertEqual(self.workspace.mod_table.selection(), (record.id,))
        self.assertFalse(record.installed)
        self.assertIsNone(self.workspace.manager.current_game_root)
        self.assertFalse(self.workspace.loader_confirmed.get())
        self.assertFalse(self.manager.mods())
        with self.assertRaises(Exception):
            self.workspace.import_archive_path(archive, game_id='nioh2_pc')
        self.assertEqual(self.workspace.manager.game_id, 'nioh3_pc')

    def test_nonwindows_workspace_keeps_library_planning_and_blocks_deployment_callbacks(self):
        from koei_editor.shared.mod_manager import mod_manager_host_capabilities
        capability = mod_manager_host_capabilities()
        capability['documented_game_deployment'] = False
        capability['message'] = 'Procedural host: library only; deployment unavailable.'
        with patch('koei_editor.shared.mod_manager_gui.mod_manager_host_capabilities', return_value=capability):
            self.workspace.refresh()
            self.assertEqual(str(self.workspace.import_button.cget('state')), 'normal')
            self.assertEqual(str(self.workspace.apply_profile_button.cget('state')), 'disabled')
            self.workspace.loader_confirmed.set(True)
            with self.assertRaisesRegex(ValueError, 'deployment unavailable'):
                self.workspace._require_loader_confirmation()

    def test_wrapped_rows_do_not_share_column_widths_and_reuse_their_containers(self):
        holder = ttk.Frame(self.root)
        holder.pack(fill='x')
        buttons = tuple(ttk.Button(holder, text=text) for text in ('A', 'B', 'C' * 30, 'D' * 30))
        width = sum(button.winfo_reqwidth() + 10 for button in buttons[:3])
        self.root.geometry(f'{width}x240')
        self.root.deiconify()
        self.workspace._flow_buttons(buttons, width)
        self.root.update()
        self.assertEqual(len({str(button.grid_info()['in']) for button in buttons}), 2)
        for button in buttons:
            self.assertLessEqual(button.winfo_rootx() + button.winfo_width(),
                                 holder.winfo_rootx() + width)
        containers = tuple(holder._mod_flow_rows)
        self.workspace._flow_buttons(buttons, width * 2)
        self.root.update()
        self.assertEqual(len({str(button.grid_info()['in']) for button in buttons}), 1)
        self.assertFalse(containers[1].winfo_ismapped())
        self.workspace._flow_buttons(buttons, width)
        self.root.update()
        self.assertEqual(tuple(holder._mod_flow_rows), containers)

    def test_small_viewport_keeps_wrapped_actions_visible_and_form_scrollable(self):
        old_scaling = self.root.tk.call('tk', 'scaling')
        self.addCleanup(lambda: self.root.winfo_exists() and self.root.tk.call('tk', 'scaling', old_scaling))
        self.root.tk.call('tk', 'scaling', float(old_scaling) * 1.4)
        style = __import__('tkinter.ttk', fromlist=['Style']).Style(self.root)
        style.configure('TButton', font=('DejaVu Sans', 14))
        style.configure('TLabel', font=('DejaVu Sans', 14))
        self.root.geometry('780x680')
        self.root.deiconify()
        self.workspace.frame.pack(fill='both', expand=True)
        self.workspace.select_game('nioh3_pc')
        self.workspace.import_button.configure(text='Mod-ZIP hinzufügen…')
        self.workspace.toggle_enabled_button.configure(text='Im Profil aktivieren')
        self.workspace.remove_button.configure(text='Aus der Bibliothek entfernen')
        self.root.update()
        self.workspace._responsive_layout()
        self.root.update()
        client_left = self.root.winfo_rootx()
        client_top = self.root.winfo_rooty()
        for button in self.workspace._action_buttons:
            with self.subTest(button=button.cget('text')):
                self.assertGreaterEqual(button.winfo_rootx(), client_left)
                self.assertGreaterEqual(button.winfo_rooty(), client_top)
                self.assertLessEqual(button.winfo_rootx() + button.winfo_width(), client_left + 780)
                self.assertLessEqual(button.winfo_rooty() + button.winfo_height(), client_top + 680)
        rows = {str(button.grid_info()['in']) for button in self.workspace._action_buttons}
        self.assertGreater(len(rows), 1)
        for row in self.workspace.actions._mod_flow_rows:
            if row.winfo_ismapped():
                self.assertLessEqual(row.winfo_reqwidth(), self.workspace.actions.winfo_width())
        canvas = self.workspace.content_canvas
        self.assertLessEqual(self.workspace.content.winfo_width(), canvas.winfo_width())
        # Font metrics can make the complete form fit at 780x680 (notably
        # Tk 9). Test scrolling with an explicitly shorter real viewport,
        # while preserving the minimum-window action bounds checked above.
        chrome_height = self.root.winfo_height() - canvas.winfo_height()
        form_height = self.workspace.content.winfo_reqheight()
        self.root.geometry(f'780x{chrome_height + max(40, form_height // 2)}')
        self.root.update()
        self.assertLess(canvas.winfo_height(), self.workspace.content.winfo_reqheight())
        self.assertGreater(canvas.bbox('all')[3], canvas.winfo_height())
        canvas.yview_moveto(1)
        self.root.update()
        self.assertGreater(canvas.yview()[0], 0)
