"""Actual Tk diagnostic cards, worker isolation, cancellation and guarded open."""
import json
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from koei_editor.games.dw7xl import dw7xl_parser as native
from koei_editor.shared import save_doctor as backend
from koei_editor.shared.appearance import THEMES
from koei_editor.shared.save_doctor_gui import SaveDoctorWorkspace
from tests.test_dw7xl_format import synthetic_raw


class SaveDoctorGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = synthetic_raw()

    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.geometry('1100x850')
        self.addCleanup(self.root.destroy)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name).resolve()
        self.source = self.folder / 'player-private-copy.dat'
        self.source.write_bytes(self.raw)
        self.opened = []
        self.workspace = SaveDoctorWorkspace(self.root, self.root,
            lambda game, path: self.opened.append((game, path, threading.get_ident())))
        self.workspace.frame.pack(fill='both', expand=True)
        self.workspace.game.set(next(label for label, value in self.workspace._games.items() if value == 'dw7xl'))
        self.workspace.path.set(str(self.source))
        self.root.update()
        self.addCleanup(self.workspace.close)

    def finish(self):
        deadline = time.monotonic() + 10
        while self.workspace.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.005)
        self.assertFalse(self.workspace.busy, 'Save Doctor worker did not finish')
        self.root.update()

    def check(self):
        self.workspace.diagnose()
        self.finish()
        self.assertTrue(self.workspace.prepared.qualified)

    def test_actual_native_check_cards_search_detail_and_main_thread_open(self):
        main = threading.get_ident()
        reads = []
        read = native.read_save
        def observed(*args, **kwargs):
            reads.append(threading.get_ident())
            return read(*args, **kwargs)
        with patch.object(native, 'read_save', side_effect=observed):
            self.check()
            self.assertTrue(reads)
            self.assertTrue(all(identifier != main for identifier in reads))
            self.workspace.filter.set('Not established')
            self.assertTrue(self.workspace.visible_findings)
            self.assertTrue(all(item.state == 'unknown' for item in self.workspace.visible_findings))
            self.workspace.search.set('checksum')
            self.assertEqual([item.code for item in self.workspace.visible_findings], ['integrity.unreported'])
            self.workspace.select_finding(self.workspace.visible_findings[0])
            self.assertIn('no independent checksum claim', self.workspace.detail.get('1.0', 'end'))
            before = len(reads)
            self.workspace.open_copy()
            self.finish()
        self.assertGreater(len(reads), before)
        self.assertEqual(self.opened, [('dw7xl', self.source, main)])
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertEqual(list(self.folder.iterdir()), [self.source])

    def test_failed_native_check_has_actionable_cards_and_no_open(self):
        self.source.write_bytes(bytes([self.raw[0] ^ 1]) + self.raw[1:])
        self.workspace.diagnose()
        self.finish()
        self.assertFalse(self.workspace.prepared.qualified)
        self.assertEqual(str(self.workspace.open_button['state']), 'disabled')
        self.workspace.filter.set('Needs attention')
        self.assertIn('native.checksum_rejected', {item.code for item in self.workspace.visible_findings})
        self.assertIn('No checksum repair', self.workspace.detail.get('1.0', 'end'))
        self.workspace.open_copy()
        self.assertFalse(self.opened)

    def test_theme_search_and_resize_do_not_reparse_or_change_diagnostics(self):
        self.check()
        frozen = backend.report(self.workspace.prepared)
        with patch.object(native, 'read_save', side_effect=AssertionError('Appearance read a save')):
            for name in ('Dark', 'Light', 'Dark'):
                self.workspace.apply_theme(THEMES[name])
                self.workspace.search.set('native')
                self.root.geometry('850x700')
                self.root.update()
                self.assertEqual(self.workspace.canvas.cget('background'), THEMES[name]['background'])
                self.assertEqual(self.workspace.detail.cget('background'), THEMES[name]['surface'])
            self.workspace.search.set('')
            self.assertEqual(backend.report(self.workspace.prepared), frozen)
        self.assertGreater(self.workspace.canvas.winfo_height(), 100)
        self.assertGreater(self.workspace.canvas.winfo_width(), 100)
        self.assertEqual(self.workspace.focus_search(), 'break')

    def test_cancel_during_worker_discards_partial_result_and_has_no_pending_save_work(self):
        entered, release = threading.Event(), threading.Event()
        result = backend.diagnose('dw7xl', self.source)
        def delayed(*args, **kwargs):
            entered.set()
            release.wait(3)
            return result
        with patch('koei_editor.shared.save_doctor_gui.backend.diagnose', side_effect=delayed):
            self.workspace.diagnose()
            self.assertTrue(entered.wait(2))
            self.assertFalse(self.workspace.has_pending_work())
            self.workspace.cancel()
            release.set()
            self.finish()
        self.assertIsNone(self.workspace.prepared)
        self.assertFalse(self.opened)
        self.assertIn('cancelled', self.workspace.status.get().lower())
        self.assertEqual(str(self.workspace.export_button['state']), 'disabled')

    def test_selection_change_discards_late_worker_result(self):
        entered, release = threading.Event(), threading.Event()
        result = backend.diagnose('dw7xl', self.source)
        def delayed(*args, **kwargs):
            entered.set()
            release.wait(3)
            return result
        with patch('koei_editor.shared.save_doctor_gui.backend.diagnose', side_effect=delayed):
            self.workspace.diagnose()
            self.assertTrue(entered.wait(2))
            self.workspace.path.set(str(self.folder / 'another.dat'))
            release.set()
            self.finish()
        self.assertIsNone(self.workspace.prepared)
        self.assertIn('Selection changed', self.workspace.status.get())
        self.assertFalse(self.workspace.visible_findings)

    def test_stale_copy_never_reaches_editor_and_error_dialog_runs_on_tk_thread(self):
        self.check()
        self.source.write_bytes(self.raw[:-1])
        dialog_threads = []
        with patch('koei_editor.shared.save_doctor_gui.messagebox.showerror',
                   side_effect=lambda *a, **k: dialog_threads.append(threading.get_ident())):
            self.workspace.open_copy()
            self.finish()
        self.assertFalse(self.opened)
        self.assertIsNone(self.workspace.prepared)
        self.assertEqual(dialog_threads, [threading.get_ident()])

    def test_editor_callback_rejection_preserves_diagnostic_and_session(self):
        self.check()
        original = self.workspace.prepared
        self.workspace.on_open = lambda game, path: False
        self.workspace.open_copy()
        self.finish()
        self.assertIs(self.workspace.prepared, original)
        self.assertIn('kept its current session', self.workspace.status.get())
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_report_export_is_atomic_background_work_and_privacy_safe(self):
        self.check()
        target = self.folder / 'result.doctor.json'
        entered, release = threading.Event(), threading.Event()
        export = backend.export_report
        def delayed(*args, **kwargs):
            entered.set()
            release.wait(3)
            return export(*args, **kwargs)
        with patch('koei_editor.shared.save_doctor_gui.filedialog.asksaveasfilename', return_value=str(target)), \
                patch('koei_editor.shared.save_doctor_gui.backend.export_report', side_effect=delayed):
            self.workspace.export()
            self.assertTrue(entered.wait(2))
            self.assertTrue(self.workspace.has_pending_work())
            self.assertEqual(str(self.workspace.cancel_button['state']), 'disabled')
            release.set()
            self.finish()
        self.assertFalse(self.workspace.has_pending_work())
        report = json.loads(target.read_text())
        self.assertTrue(report['historical_snapshot'])
        self.assertFalse(report['repairs_attempted'])
        self.assertNotIn(self.source.name, target.read_text())
        self.assertNotIn(str(self.folder), target.read_text())
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_close_cancels_worker_and_discards_late_callback(self):
        self.check()
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        source = self.source
        def delayed(*args, **kwargs):
            entered.set()
            release.wait(3)
            finished.set()
            return source
        with patch('koei_editor.shared.save_doctor_gui.backend.requalify', side_effect=delayed):
            self.workspace.open_copy()
            self.assertTrue(entered.wait(2))
            self.workspace.close()
            release.set()
            self.assertTrue(finished.wait(2))
            self.root.update()
        self.assertTrue(self.workspace._cancel.is_set())
        self.assertIsNone(self.workspace._poll_id)
        self.assertFalse(self.opened)

    def test_direct_root_destruction_stops_progress_animation_without_tcl_background_errors(self):
        other = tk.Tk()
        errors = []
        other.tk.createcommand('doctor_background_error', lambda message: errors.append(message))
        other.tk.eval('proc bgerror {message} {doctor_background_error $message}')
        workspace = SaveDoctorWorkspace(other, other)
        workspace.game.set(next(label for label, value in workspace._games.items() if value == 'dw7xl'))
        workspace.path.set(str(self.source))
        result = backend.diagnose('dw7xl', self.source)
        entered, release = threading.Event(), threading.Event()
        def delayed(*args, **kwargs):
            entered.set()
            release.wait(3)
            return result
        with patch('koei_editor.shared.save_doctor_gui.backend.diagnose', side_effect=delayed):
            workspace.diagnose()
            self.assertTrue(entered.wait(2))
            other.update()
            other.destroy()
            release.set()
            deadline = time.monotonic() + 0.15
            while time.monotonic() < deadline:
                self.root.update()
                time.sleep(0.005)
        self.assertTrue(workspace._closed)
        self.assertTrue(workspace._cancel.is_set())
        self.assertEqual(errors, [])
