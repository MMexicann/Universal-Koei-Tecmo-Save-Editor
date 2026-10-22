"""Actual Tk scanning, cancellation, stale-result guards and editor delegation."""
from dataclasses import replace
from pathlib import Path
import tempfile
from types import SimpleNamespace
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.games.deception4_ps3 import parser
from koei_editor.shared import save_library as backend
from koei_editor.shared.save_library_gui import SaveLibraryWorkspace
from tests import test_ps3_expansion as ps3_helpers
from tests.test_ps3_new_families import fixture


class SaveLibraryGuiTests(unittest.TestCase):
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
        self.raw = fixture(parser)
        self.first = self.folder / 'first.bin'
        self.second = self.folder / 'second.bin'
        self.first.write_bytes(self.raw)
        self.second.write_bytes(self.raw)
        (self.folder / 'PARAM.SFO').write_bytes(ps3_helpers.PS3ContextTests.metadata('NPUB31442-GAMEDATA-10'))
        self.opened = []
        self.workspace = SaveLibraryWorkspace(self.root, self.root, lambda game, path: self.opened.append((game, path, threading.get_ident())))
        self.workspace.game.set(next(label for label, game in self.workspace._games.items() if game == parser.GAME_ID))
        self.workspace.folder.set(str(self.folder))

    def finish(self):
        deadline = time.monotonic() + 10
        while self.workspace.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.005)
        self.assertFalse(self.workspace.busy, 'Save Library worker did not finish')
        self.root.update()

    def select(self, name):
        index = next(index for index, entry in enumerate(self.workspace.prepared.entries) if entry.relative_path == name)
        self.workspace.table.selection_set(str(index))
        self.workspace.selection_changed()

    def test_scan_search_filter_sort_open_and_source_preservation(self):
        main_thread = threading.get_ident()
        threads = []
        original = parser.read_save
        def read(*args, **kwargs):
            threads.append(threading.get_ident())
            return original(*args, **kwargs)
        with patch.object(parser, 'read_save', side_effect=read):
            self.workspace.scan()
            self.finish()
            self.assertEqual(len(self.workspace.table.get_children()), 2)
            self.assertTrue(all(identity != main_thread for identity in threads))
            self.workspace.search.set('second')
            self.assertEqual(len(self.workspace.table.get_children()), 1)
            self.workspace.filter.set('Not qualified')
            self.assertFalse(self.workspace.table.get_children())
            self.workspace.filter.set('Identical gameplay files')
            self.assertEqual(len(self.workspace.table.get_children()), 1)
            self.workspace.search.set('')
            self.workspace.sort.set('Identical files first')
            self.select('second.bin')
            self.assertEqual(str(self.workspace.open_button['state']), 'normal')
            before = len(threads)
            self.workspace.open_selected()
            self.finish()
        self.assertEqual(len(threads), before + 1)
        self.assertEqual(self.opened, [(parser.GAME_ID, self.second.resolve(), main_thread)])
        self.assertEqual(self.first.read_bytes(), self.raw)
        self.assertEqual(self.second.read_bytes(), self.raw)
        self.assertEqual(len(tuple(self.folder.iterdir())), 3)

    def test_stale_selected_copy_or_original_context_never_reaches_editor(self):
        self.workspace.scan()
        self.finish()
        self.select('first.bin')
        self.first.write_bytes(self.raw[:-1])
        with patch('koei_editor.shared.save_library_gui.messagebox.showerror') as errors:
            self.workspace.open_selected()
            self.finish()
        self.assertTrue(errors.called)
        self.assertFalse(self.opened)
        self.assertIsNone(self.workspace.prepared)
        self.assertIn('changed', self.workspace.status.get())

    def test_changed_selection_discards_late_scan_without_tk_worker_calls(self):
        entered, release = threading.Event(), threading.Event()
        prepared = backend.scan(parser.GAME_ID, self.folder)
        def delayed(*args, **kwargs):
            entered.set()
            release.wait(5)
            return prepared
        with patch('koei_editor.shared.save_library_gui.backend.scan', side_effect=delayed):
            self.workspace.scan()
            self.assertTrue(entered.wait(2))
            self.workspace.folder.set(str(self.folder / 'another-folder'))
            release.set()
            self.finish()
        self.assertIsNone(self.workspace.prepared)
        self.assertFalse(self.workspace.table.get_children())
        self.assertIn('Selections changed', self.workspace.status.get())
        self.assertFalse(self.opened)

    def test_cancel_open_after_qualification_prevents_callback(self):
        self.workspace.scan()
        self.finish()
        self.select('first.bin')
        entered, release = threading.Event(), threading.Event()
        original = backend.requalify
        def delayed(*args, **kwargs):
            document = original(*args, **kwargs)
            entered.set()
            release.wait(5)
            return document
        with patch('koei_editor.shared.save_library_gui.backend.requalify', side_effect=delayed):
            self.workspace.open_selected()
            self.assertTrue(entered.wait(2))
            self.workspace.cancel()
            release.set()
            self.finish()
        self.assertFalse(self.opened)
        self.assertIn('Opening cancelled', self.workspace.status.get())
        self.assertIsNotNone(self.workspace.prepared)

    def test_cancel_after_open_result_is_queued_prevents_callback(self):
        self.workspace.scan()
        self.finish()
        self.select('first.bin')
        self.assertEqual(self.workspace.selected_entry().status, 'qualified')
        queued = threading.Event()
        original_queue = self.workspace._results
        class NotifyingQueue:
            def put(self, value):
                original_queue.put(value)
                queued.set()

            def get_nowait(self):
                return original_queue.get_nowait()
        self.workspace._results = NotifyingQueue()
        self.workspace.open_selected()
        # Do not service Tk yet: the worker's result captures cancelled=False.
        self.assertTrue(queued.wait(2), 'Open qualification did not queue its result')
        self.workspace.cancel()
        self.finish()
        self.assertFalse(self.opened)
        self.assertIn('Opening cancelled', self.workspace.status.get())
        self.assertIsNotNone(self.workspace.prepared)

    def test_editor_callback_rejection_and_failure_have_accurate_private_status(self):
        self.workspace.scan()
        self.finish()
        self.select('first.bin')
        self.workspace.on_open = lambda _game_id, _path: False
        self.workspace.open_selected()
        self.finish()
        self.assertIn('cancelled or rejected', self.workspace.status.get())
        self.assertIsNotNone(self.workspace.prepared)
        self.select('first.bin')
        self.workspace.on_open = lambda _game_id, _path: True
        self.workspace.open_selected()
        self.finish()
        self.assertIn('Copy opened', self.workspace.status.get())
        def failed(_game_id, _path):
            raise RuntimeError('private-player-save-path')
        self.workspace.on_open = failed
        self.select('first.bin')
        with patch('koei_editor.shared.save_library_gui.messagebox.showerror') as errors:
            self.workspace.open_selected()
            self.finish()
        errors.assert_called_once()
        self.assertNotIn('private-player-save-path', str(errors.call_args))
        self.assertNotIn('private-player-save-path', self.workspace.status.get())
        self.assertIn('could not open', self.workspace.status.get())

    def test_search_focus_selects_the_query_without_changing_results(self):
        self.workspace.search.set('existing query')
        self.assertEqual(self.workspace.focus_search(), 'break')
        self.assertTrue(self.workspace.search_entry.selection_present())
        self.assertEqual(self.workspace.search.get(), 'existing query')

    def test_real_application_minimum_size_keeps_footer_and_paging_visible(self):
        from koei_editor.application import Application
        app = Application(self.root, preferences_path=self.folder / 'prefs.json', persist_preferences=False)
        app.show_save_library()
        workspace = app.save_library
        workspace.game.set(next(label for label, game in workspace._games.items() if game == parser.GAME_ID))
        workspace.folder.set(str(self.folder))
        prepared = backend.scan(parser.GAME_ID, self.folder)
        # More than one page makes pagination useful while the selected real
        # entry exercises the longer qualified/context guidance.
        entries = prepared.entries + tuple(replace(prepared.entries[0], relative_path=f'copy-{index:03}.bin')
                                           for index in range(150))
        workspace.prepared = replace(prepared, entries=entries)
        workspace.refresh()
        workspace.table.selection_set(workspace.table.get_children()[0])
        workspace.selection_changed()
        workspace.status.set('Scan finished: 152 qualified of 152 candidate files; '
                             '0 directories excluded. Qualification is specific to the chosen profile.')
        self.root.deiconify()
        for width, height in ((1080, 820), (1180, 930)):
            with self.subTest(width=width, height=height):
                self.root.geometry(f'{width}x{height}')
                self.root.update()
                bottom = self.root.winfo_rooty() + self.root.winfo_height()
                right = self.root.winfo_rootx() + self.root.winfo_width()
                # Preserve access to every form, filter, management and batch
                # control as well as paging at the application's minimum size.
                visible_controls = (*workspace.controls,
                                    *workspace.management_button.master.winfo_children(),
                                    *workspace.select_matches_button.master.winfo_children(),
                                    *workspace.search_entry.master.winfo_children(),
                                    workspace.previous, workspace.next, workspace.page_label,
                                    workspace.detail_label, workspace.guidance_label)
                for widget in visible_controls:
                    self.assertTrue(widget.winfo_ismapped(), str(widget))
                    self.assertGreaterEqual(widget.winfo_height(), widget.winfo_reqheight(), str(widget))
                    self.assertGreaterEqual(widget.winfo_width(), widget.winfo_reqwidth(), str(widget))
                    self.assertGreaterEqual(widget.winfo_rootx(), self.root.winfo_rootx(), str(widget))
                    self.assertGreaterEqual(widget.winfo_rooty(), self.root.winfo_rooty(), str(widget))
                    self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(), bottom)
                    self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(), right)
                self.assertGreaterEqual(workspace.table.winfo_height(), 100)
                self.assertLessEqual(workspace.table.winfo_rooty() + workspace.table.winfo_height(),
                                     workspace.detail_label.winfo_rooty())
                self.assertLessEqual(int(workspace.guidance_label.cget('wraplength')),
                                     workspace.footer.winfo_width())
                self.assertEqual(str(workspace.next['state']), 'normal')
                workspace.change_page(1)
                self.assertEqual(workspace.page, 1)
                self.assertEqual(str(workspace.previous['state']), 'normal')
                workspace.change_page(-1)

    def test_cancel_scan_retains_only_complete_qualified_results_and_partial_label(self):
        entered, release = threading.Event(), threading.Event()
        original = backend.scan
        def delayed(*args, **kwargs):
            entered.set()
            release.wait(5)
            return original(*args, **kwargs)
        with patch('koei_editor.shared.save_library_gui.backend.scan', side_effect=delayed):
            self.workspace.scan()
            self.assertTrue(entered.wait(2))
            self.workspace.cancel()
            release.set()
            self.finish()
        self.assertEqual(self.workspace.prepared.stop_reason, 'cancelled')
        self.assertEqual(self.workspace.prepared.entries, ())
        self.assertIn('partial results', self.workspace.status.get())

    def test_paging_all_results_and_sort_keeps_stable_entry_identity(self):
        prepared = backend.scan(parser.GAME_ID, self.folder)
        entry = prepared.entries[0]
        entries = tuple(replace(entry, relative_path=f'copy-{index:03}.bin', size_bytes=index + 1,
                                modified_ns=index * 1_000_000_000) for index in range(350))
        self.workspace.prepared = replace(prepared, entries=entries)
        self.workspace.refresh()
        self.assertEqual(len(self.workspace.table.get_children()), 100)
        self.workspace.change_page(3)
        self.assertEqual(len(self.workspace.table.get_children()), 50)
        self.assertEqual(self.workspace.table.get_children()[0], '300')
        self.workspace.sort.set('Largest first')
        self.assertEqual(self.workspace.table.get_children()[0], '349')
        self.workspace.search.set('copy-111')
        self.assertEqual(self.workspace.table.get_children(), ('111',))
        self.workspace.table.selection_set('111')
        self.assertEqual(self.workspace.selected_entry().relative_path, 'copy-111.bin')
        self.assertEqual(self.workspace.page, 0)
        self.workspace.apply_theme({})

    def test_missing_selection_and_foreign_file_disable_open_and_error_privacy(self):
        self.first.write_bytes(b'foreign')
        self.second.write_bytes(b'foreign')
        self.workspace.scan()
        self.finish()
        self.select('first.bin')
        self.assertEqual(str(self.workspace.open_button['state']), 'disabled')
        self.workspace.open_selected()
        self.assertFalse(self.workspace.busy)
        self.workspace.folder.set('')
        with patch('koei_editor.shared.save_library_gui.messagebox.showinfo') as info:
            self.workspace.scan()
        self.assertTrue(info.called)
        self.workspace.folder.set(str(self.folder))
        with (patch('koei_editor.shared.save_library_gui.backend.scan', side_effect=RuntimeError('secret-owner-private-path')),
              patch('koei_editor.shared.save_library_gui.messagebox.showerror') as error):
            self.workspace.scan()
            self.finish()
        self.assertNotIn('secret-owner-private-path', self.workspace.status.get())
        self.assertNotIn('secret-owner-private-path', str(error.call_args))

    def test_destroy_cancels_worker_and_late_result_cannot_open_an_editor(self):
        entered, release = threading.Event(), threading.Event()
        original = backend.scan
        def delayed(*args, **kwargs):
            entered.set()
            release.wait(5)
            return original(*args, **kwargs)
        with patch('koei_editor.shared.save_library_gui.backend.scan', side_effect=delayed):
            self.workspace.scan()
            self.assertTrue(entered.wait(2))
            self.workspace.frame.destroy()
            self.assertTrue(self.workspace._cancel.is_set())
            self.assertTrue(self.workspace._closed)
            release.set()
        self.root.update()
        self.assertFalse(self.opened)
    def test_selection_survives_sort_and_pages_and_filter_clears_hidden_selection(self):
        prepared = backend.scan(parser.GAME_ID, self.folder)
        entries = tuple(replace(prepared.entries[0], relative_path=f'copy-{index:03}.bin', size_bytes=index + 1)
                        for index in range(250))
        self.workspace.prepared = replace(prepared, entries=entries)
        self.workspace.refresh()
        self.workspace.table.selection_set(('0', '5'))
        self.workspace.selection_changed()
        self.workspace.change_page(1)
        self.workspace.table.selection_set(('100',))
        self.workspace.selection_changed()
        self.assertEqual([entry.relative_path for entry in self.workspace.selected_entries()],
                         ['copy-000.bin', 'copy-005.bin', 'copy-100.bin'])
        self.workspace.sort.set('Largest first')
        self.assertEqual(len(self.workspace.selected_entries()), 3)
        self.assertEqual(str(self.workspace.open_button['state']), 'disabled')
        self.assertEqual(str(self.workspace.recheck_button['state']), 'normal')
        self.assertIn('3 copies selected', self.workspace.detail.get())
        self.workspace.search.set('copy-111')
        self.assertEqual(self.workspace.selected_entries(), ())
        self.workspace.select_matches()
        self.assertEqual(self.workspace.selected_entry().relative_path, 'copy-111.bin')
        self.workspace.search.set('')
        self.workspace.select_matches()
        self.assertEqual(len(self.workspace.selected_entries()), 250)
        self.workspace.clear_selection()
        self.assertEqual(self.workspace.selected_entries(), ())

    def test_batch_rechecks_real_sources_off_tk_thread_and_keeps_failed_copy_visible(self):
        self.workspace.scan()
        self.finish()
        self.workspace.select_matches()
        self.first.write_bytes(self.raw[:-1])
        main_thread, calls = threading.get_ident(), []
        original = backend.requalify
        def rechecked(*args, **kwargs):
            calls.append(threading.get_ident())
            return original(*args, **kwargs)
        with patch.object(backend, 'requalify', side_effect=rechecked):
            self.workspace.recheck_selected()
            self.finish()
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(thread != main_thread for thread in calls))
        self.assertEqual(self.workspace.check_results, {'first.bin': 'not_qualified', 'second.bin': 'qualified'})
        self.assertIn('1 qualified of 2 checked', self.workspace.status.get())
        self.assertEqual(len(self.workspace.table.get_children()), 2)
        self.assertEqual(self.second.read_bytes(), self.raw)
        self.assertFalse(self.opened)
        self.workspace.invalidate()
        self.assertFalse(self.workspace.check_results)
        self.assertEqual(self.workspace.selected_entries(), ())

    def test_management_callback_uses_explicit_original_selection_on_tk_thread(self):
        self.workspace.scan()
        self.finish()
        self.workspace.select_matches()
        managed = []
        self.workspace.on_manage = lambda result, entries: managed.append((result, entries, threading.get_ident()))
        self.workspace.manage_selected()
        self.assertEqual(len(managed), 1)
        self.assertIs(managed[0][0], self.workspace.prepared)
        self.assertEqual({entry.relative_path for entry in managed[0][1]}, {'first.bin', 'second.bin'})
        self.assertEqual(managed[0][2], threading.get_ident())
        self.assertFalse(self.opened)

    def test_folder_status_and_ungrouped_filters_change_actual_table_rows(self):
        nested = self.folder / 'chapter' / 'nested'
        nested.mkdir(parents=True)
        (nested / 'bad.bin').write_bytes(b'damaged')
        self.workspace.recursive.set(True)
        self.workspace.scan()
        self.finish()
        self.assertIn('chapter', self.workspace.folder_filter['values'])
        self.workspace.subfolder.set('chapter')
        self.assertEqual(len(self.workspace.table.get_children()), 1)
        self.workspace.filter.set('Qualified')
        self.assertEqual(self.workspace.table.get_children(), ())
        self.workspace.filter.set('No identical file found')
        self.assertEqual(len(self.workspace.table.get_children()), 1)
        self.workspace.subfolder.set('All folders')
        self.workspace.filter.set('Identical gameplay files')
        self.assertEqual(len(self.workspace.table.get_children()), 2)


    def test_tools_are_available_before_scanning_and_reuse_management_window(self):
        instances = []
        class ManagementWindow:
            def __init__(inner, root, **kwargs):
                inner.requests = [(root, kwargs)]
                instances.append(inner)
            def show(inner, **kwargs):
                inner.requests.append(kwargs)
            def apply_theme(inner, palette):
                inner.palette = palette
        module = SimpleNamespace(SaveManagementWindow=ManagementWindow)
        with patch.dict('sys.modules', {'koei_editor.shared.save_management_gui': module}):
            self.workspace.apply_theme({'background': '#123456'})
            self.workspace.management_button.invoke()
            self.assertEqual(instances[0].palette, {'background': '#123456'})
            self.workspace.apply_theme({'background': '#abcdef'})
            self.assertEqual(instances[0].palette, {'background': '#abcdef'})
            self.assertIs(self.workspace.management, instances[0])
            self.assertEqual(instances[0].requests[0][1], {'game_id': parser.GAME_ID, 'paths': ()})
            self.workspace.scan()
            self.finish()
            self.workspace.select_matches()
            self.workspace.manage_selected()
            self.assertEqual(len(instances), 1)
            self.assertEqual(instances[0].requests[1]['game_id'], parser.GAME_ID)
            managed_paths = instances[0].requests[1]['paths']
            self.assertEqual(len(managed_paths), 2)
            # Windows runner fixtures can use 8.3 ancestors while the library
            # returns canonical paths. Compare file identity for both copies.
            for original in (self.first, self.second):
                self.assertEqual(sum(path.samefile(original) for path in managed_paths), 1)
            self.assertFalse(self.opened)
            instances[0]._closed = True
            self.workspace.show_management()
            self.assertEqual(len(instances), 2)
            self.assertIs(self.workspace.management, instances[1])

    def test_cancel_batch_recheck_preserves_complete_outcomes_and_never_opens_editor(self):
        self.workspace.scan()
        self.finish()
        self.workspace.select_matches()
        entered, release = threading.Event(), threading.Event()
        original = backend.requalify
        calls = []
        def delayed(*args, **kwargs):
            calls.append(True)
            if len(calls) == 2:
                entered.set()
                release.wait(5)
            return original(*args, **kwargs)
        with patch.object(backend, 'requalify', side_effect=delayed):
            self.workspace.recheck_selected()
            self.assertTrue(entered.wait(2))
            self.workspace.cancel()
            release.set()
            self.finish()
        self.assertEqual(len(self.workspace.check_results), 1)
        self.assertIn('cancelled (partial results)', self.workspace.status.get())
        self.assertFalse(self.opened)
        self.assertEqual(self.first.read_bytes(), self.raw)
        self.assertEqual(self.second.read_bytes(), self.raw)

    def test_compact_header_scrolling_resize_state_theme_and_callback_cleanup(self):
        from koei_editor.application import Application
        app = Application(self.root, preferences_path=self.folder / 'prefs.json', persist_preferences=False)
        app.show_save_library()
        workspace = app.save_library
        workspace.game.set(next(label for label, game in workspace._games.items() if game == parser.GAME_ID))
        workspace.folder.set(str(self.folder))
        prepared = backend.scan(parser.GAME_ID, self.folder)
        entries = prepared.entries + tuple(replace(prepared.entries[0], relative_path=f'copy-{index:03}.bin')
                                           for index in range(150))
        workspace.prepared = replace(prepared, entries=entries)
        workspace.search.set('bin qualified')
        workspace.filter.set('Qualified')
        workspace.sort.set('Newest first')
        workspace.table.selection_set(workspace.table.get_children()[:2])
        workspace.selection_changed()
        workspace.status.set('Scan finished: 152 qualified of 152 candidate files; '
                             '0 directories excluded. Qualification is specific to the chosen profile.')
        selected = workspace.selected_entries()
        inventory = workspace.prepared
        # Exercise the separately composed shell minimum without changing the
        # application's shell contract in this Library-only regression.
        self.root.minsize(780, 680)
        self.root.deiconify()
        header_controls = (workspace.selector, workspace.folder_entry, workspace.browse_button,
                           workspace.recursive_button, *workspace.management_button.master.winfo_children(),
                           *workspace.search_entry.master.winfo_children(),
                           *(label for label in workspace._wrapped_labels if label.master is workspace.header.content))
        pinned_controls = (*workspace.select_matches_button.master.winfo_children(), workspace.previous,
                           workspace.next, workspace.page_label, workspace.detail_label, workspace.guidance_label)
        for language, text_size in (('English', '100%'), ('English', '120%'), ('English', '140%'),
                                    ('Deutsch', '140%'), ('English', '100%')):
            app.language_choice.set(language)
            app.change_language()
            app.text_size_choice.set(text_size)
            app.change_text_size()
            for width, height in ((1080, 820), (780, 680), (1180, 930), (780, 680)):
                with self.subTest(language=language, text_size=text_size, width=width, height=height):
                    self.root.geometry(f'{width}x{height}')
                    self.root.update()
                    self.assertIs(workspace.prepared, inventory)
                    self.assertEqual(workspace.selected_entries(), selected)
                    self.assertEqual((workspace.search.get(), workspace.filter.get(), workspace.sort.get()),
                                     ('bin qualified', 'Qualified', 'Newest first'))
                    self.assertEqual(int(workspace.folder_filter.grid_info()['row']), int(workspace._narrow_filters))
                    self.assertEqual(int(workspace.sort_selector.grid_info()['row']), int(workspace._narrow_filters))
                    for buttons in (workspace._header_actions, workspace._batch_actions):
                        required = sum(button.winfo_reqwidth() for button in buttons) + 8 * (len(buttons) - 1)
                        wrapped = required > buttons[0].master.winfo_width()
                        self.assertEqual({int(button.grid_info()['row']) for button in buttons},
                                         {0, 1} if wrapped else {0})
                    self.assertGreaterEqual(workspace.table.winfo_height(), 100)
                    self.assertTrue(workspace.horizontal_scrollbar.winfo_ismapped())
                    self.assertLessEqual(workspace.table.winfo_rooty() + workspace.table.winfo_height(),
                                         workspace.footer.winfo_rooty())
                    for widget in pinned_controls:
                        self.assertTrue(widget.winfo_ismapped())
                        self.assertGreaterEqual(widget.winfo_width(), widget.winfo_reqwidth())
                        self.assertGreaterEqual(widget.winfo_height(), widget.winfo_reqheight())
                        self.assertGreaterEqual(widget.winfo_rootx(), self.root.winfo_rootx())
                        self.assertGreaterEqual(widget.winfo_rooty(), self.root.winfo_rooty())
                        self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                             self.root.winfo_rootx() + self.root.winfo_width())
                        self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                             self.root.winfo_rooty() + self.root.winfo_height())
                    canvas = workspace.header.canvas
                    if width == 780:
                        self.assertLess(canvas.yview()[1] - canvas.yview()[0], 1)
                    elif (text_size == '100%'
                          and canvas.winfo_height() + 1 >= workspace.header.content.winfo_reqheight()):
                        self.assertEqual(canvas.yview(), (0.0, 1.0))
                    for widget in header_controls:
                        workspace.header.reveal(widget)
                        self.root.update()
                        self.assertTrue(widget.winfo_ismapped())
                        self.assertGreaterEqual(widget.winfo_width(), widget.winfo_reqwidth())
                        self.assertGreaterEqual(widget.winfo_height(), widget.winfo_reqheight())
                        self.assertGreaterEqual(widget.winfo_rootx(), canvas.winfo_rootx())
                        self.assertGreaterEqual(widget.winfo_rooty(), canvas.winfo_rooty())
                        self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                             canvas.winfo_rootx() + canvas.winfo_width())
                        self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                             canvas.winfo_rooty() + canvas.winfo_height())
        # Keyboard focus reveals a lower form control without a direct reveal.
        workspace.header.canvas.yview_moveto(0)
        self.root.focus_force()
        workspace.sort_selector.focus_force()
        self.root.update()
        self.assertIs(self.root.focus_get(), workspace.sort_selector)
        self.assertGreater(workspace.header.canvas.yview()[0], 0)
        self.assertLessEqual(workspace.sort_selector.winfo_rooty() + workspace.sort_selector.winfo_height(),
                             canvas.winfo_rooty() + canvas.winfo_height())
        app.apply_theme('Dark')
        self.assertEqual(canvas.cget('background'), workspace._palette['background'])
        self.root.update()
        workspace._schedule_layout()
        workspace.header._schedule()
        workspace.header._focus(SimpleNamespace(widget=workspace.selector))
        callbacks = (workspace._layout_id, workspace.header._pending, workspace.header._focus_pending)
        tag = workspace.header._tag
        self.assertTrue(self.root.bind_class(tag, '<MouseWheel>'))
        workspace.frame.destroy()
        self.assertTrue(workspace._closed)
        self.assertIsNone(workspace._layout_id)
        pending = self.root.tk.call('after', 'info')
        for callback in callbacks:
            self.assertNotIn(callback, pending)
        for sequence in ('<MouseWheel>', '<FocusIn>', '<Configure>', '<Prior>', '<Next>'):
            self.assertFalse(self.root.bind_class(tag, sequence))
