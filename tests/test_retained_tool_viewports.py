"""Real minimum-window navigation and native copy flows in retained tools."""
import json
from pathlib import Path
import tempfile
import time
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from koei_editor.application import Application
from koei_editor import conversion
from koei_editor.shared import batch_conversion
from tests.test_conversion import write_copy
from tests.test_origins_parser import fixture as origins_fixture


class RetainedToolViewportTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.root.destroy)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.pc = write_copy(self.folder / 'pc', 'dw6')
        self.ps3 = write_copy(self.folder / 'ps3', 'dw6_ps3', 1)
        self.originals = {path: path.read_bytes() for path in
                          (self.pc, self.ps3, self.ps3.parent / 'PARAM.SFO')}
        self.app = Application(self.root, preferences_path=self.folder / 'prefs.json',
                               persist_preferences=False)
        self.editor_source = self.folder / 'editor.dat'
        self.editor_source.write_bytes(origins_fixture())
        self.editor = self.app.select_game('origins')
        self.assertTrue(self.editor.open_path(self.editor_source))
        self.editor.stage_values({'gold': 12345})
        self.pending, self.history = dict(self.editor.changes), list(self.editor.history)

    def modes(self, show):
        for language in ('English', 'Deutsch'):
            for size in ('100%', '140%'):
                self.app.language_choice.set(language)
                self.app.change_language()
                self.app.text_size_choice.set(size)
                self.app.change_text_size()
                show()
                self.root.geometry('780x680')
                self.root.update()
                self.root.update()
                self.assertEqual((self.root.winfo_width(), self.root.winfo_height()), (780, 680))
                self.assertEqual(self.root.minsize(), (780, 680))
                yield language, size

    def finish(self, workspace):
        deadline = time.monotonic() + 20
        while workspace.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(.01)
        self.assertFalse(workspace.busy, 'Native worker did not finish.')
        self.root.update()

    def inside(self, widget):
        self.assertTrue(widget.winfo_viewable(), str(widget))
        self.assertGreater(widget.winfo_width(), 1, str(widget))
        self.assertGreater(widget.winfo_height(), 1, str(widget))
        self.assertGreaterEqual(widget.winfo_width(), widget.winfo_reqwidth(), str(widget))
        parent = widget.master
        while parent is not None:
            for coordinate, extent in (('x', 'width'), ('y', 'height')):
                lower = getattr(parent, 'winfo_root' + coordinate)()
                actual = getattr(widget, 'winfo_root' + coordinate)()
                self.assertGreaterEqual(actual, lower, (str(widget), str(parent)))
                self.assertLessEqual(actual + getattr(widget, 'winfo_' + extent)(),
                                     lower + getattr(parent, 'winfo_' + extent)(),
                                     (str(widget), str(parent)))
            if parent is self.root:
                break
            parent = parent.master

    def reachable_controls(self, workspace):
        pending = [workspace.frame]
        while pending:
            parent = pending.pop()
            pending.extend(parent.winfo_children())
            if isinstance(parent, (ttk.Button, ttk.Entry, ttk.Combobox)):
                # Disabled actions remain reachable through the scoped scrollbar;
                # enabled inputs additionally reveal themselves on real focus.
                workspace.viewport.reveal(parent)
                self.root.update()
                self.inside(parent)
                if str(parent.cget('state')) != 'disabled':
                    parent.focus_force()
                    self.root.update()
                    self.assertIs(self.root.focus_get(), parent)
                    self.inside(parent)
        self.assertEqual((self.editor.changes, self.editor.history), (self.pending, self.history))
        self.assertEqual(self.editor_source.read_bytes(), origins_fixture())
        for source, raw in self.originals.items():
            self.assertEqual(source.read_bytes(), raw)

    def test_converter_actions_and_native_review_export_queue_at_each_minimum_mode(self):
        self.app.show_converter()
        gui = self.app.converter
        gui.route.set(conversion.get_route('dw6-to-dw6_ps3').label)
        gui.source.set(str(self.pc))
        gui.template.set(str(self.ps3))
        for index, mode in enumerate(self.modes(self.app.show_converter)):
            with self.subTest(mode=mode):
                self.reachable_controls(gui)
                self.inside(gui.review_button)
                self.inside(gui.export_button)
                self.inside(gui.queue_button)
                gui.review_button.invoke()
                self.finish(gui)
                self.assertIsNotNone(gui.prepared)
                with patch('koei_editor.shared.conversion_gui.filedialog.askdirectory', return_value=str(self.folder)), \
                        patch('tkinter.simpledialog.askstring', return_value=f'converted-{index}'), \
                        patch('koei_editor.shared.conversion_gui.messagebox.showinfo'):
                    gui.export_button.invoke()
                    self.finish(gui)
                self.assertTrue((self.folder / f'converted-{index}' / 'APP.BIN').is_file())
                with patch('koei_editor.shared.batch_conversion_gui.filedialog.askdirectory', return_value=str(self.folder)), \
                        patch('koei_editor.shared.batch_conversion_gui.simpledialog.askstring', return_value=f'queued-{index}'):
                    gui.queue_button.invoke()
                self.assertIs(self.app.converter, gui)
                self.assertEqual(len(self.app.batch.specs), index + 1)
                self.app.show_converter()
                self.root.update()
                self.reachable_controls(gui)

    def test_comparison_paging_and_native_report_at_each_minimum_mode(self):
        self.app.show_comparison()
        gui = self.app.comparison
        other = self.folder / 'comparison.dat'
        other.write_bytes(origins_fixture(gold=4321, skill_points=321))
        self.originals[other] = other.read_bytes()
        gui.game.set(next(label for label, game in gui._games.items() if game == 'origins'))
        gui.first.set(str(self.editor_source))
        gui.second.set(str(other))
        for index, mode in enumerate(self.modes(self.app.show_comparison)):
            with self.subTest(mode=mode):
                self.reachable_controls(gui)
                self.inside(gui.previous)
                self.inside(gui.next)
                gui.viewport.reveal(gui.compare_button)
                self.root.update()
                gui.compare_button.invoke()
                self.finish(gui)
                self.assertGreater(len(gui.prepared.rows), 1)
                gui.page_size = 1
                gui.refresh()
                gui.next.invoke()
                self.assertEqual(gui.page, 1)
                gui.previous.invoke()
                self.assertEqual(gui.page, 0)
                self.inside(gui.previous)
                self.inside(gui.next)
                destination = self.folder / f'comparison-{index}.json'
                with patch('koei_editor.shared.comparison_gui.filedialog.asksaveasfilename', return_value=str(destination)):
                    gui.viewport.reveal(gui.export_button)
                    self.root.update()
                    gui.export_button.invoke()
                    self.finish(gui)
                self.assertTrue(destination.is_file())
                self.reachable_controls(gui)

    def test_batch_review_export_stop_and_report_controls_at_each_minimum_mode(self):
        self.app.show_batch()
        gui = self.app.batch
        for index, mode in enumerate(self.modes(self.app.show_batch)):
            with self.subTest(mode=mode):
                gui.specs = [batch_conversion.JobSpec(f'copy-{index}', 'dw6-to-dw6_ps3', self.pc,
                                                     self.ps3, self.folder / f'batch-{index}')]
                gui.invalidate()
                self.reachable_controls(gui)
                for button in (*gui.controls, gui.export_button, gui.stop_button, gui.report_button):
                    self.inside(button)
                gui.review()
                self.finish(gui)
                self.inside(gui.export_button)
                gui.export_button.invoke()
                self.inside(gui.stop_button)
                self.finish(gui)
                self.assertEqual(gui.last_report['completed'], 1)
                destination = self.folder / f'batch-report-{index}.json'
                with patch('koei_editor.shared.batch_conversion_gui.filedialog.asksaveasfilename', return_value=str(destination)):
                    gui.report_button.invoke()
                    self.finish(gui)
                self.assertTrue(json.loads(destination.read_text())['success'])
                self.reachable_controls(gui)
