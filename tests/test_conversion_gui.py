"""Real Tk asynchronous conversion, navigation, theme and command-line checks."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.application import Application
from koei_editor import conversion
from tests import test_conversion as fixtures
from tests import test_dw6_ps3 as dw6


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'A graphical display is required.')
class ConversionGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.app = Application(self.root, persist_preferences=False)
        self.app.show_converter()
        self.gui = self.app.converter

    def wait(self):
        deadline = time.monotonic() + 30
        while self.gui.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertFalse(self.gui.busy, 'Conversion worker did not finish.')
        self.root.update_idletasks()

    def select_copies(self):
        source = fixtures.write_copy(self.folder / 'source', 'dw8xl')
        template = fixtures.write_copy(self.folder / 'template', 'dw8xl_vita')
        self.gui.route.set(conversion.get_route('dw8xl-to-dw8xl_vita').label)
        self.gui.source.set(str(source))
        self.gui.template.set(str(template))

    def test_review_export_navigation_and_theme_retain_editor_sessions(self):
        editor = self.app.select_game('dw6_ps3')
        source = self.folder / 'APP.BIN'
        source.write_bytes(dw6.fixture())
        dw6.context(self.folder)
        with patch('tkinter.filedialog.askopenfilename', return_value=str(source)):
            editor.open()
        editor.changes = editor.adapter.stage(editor.document, {}, 'horse_0_speed', 500)
        self.app.show_converter()
        self.select_copies()
        self.gui.review()
        self.assertTrue(self.gui.busy)
        self.app.apply_theme('Dark')
        self.wait()
        self.assertIsNotNone(self.gui.prepared)
        self.assertIn('753,476', self.gui.preview.get('1.0', 'end'))
        with patch('tkinter.filedialog.askdirectory', return_value=str(self.folder)), \
             patch('tkinter.simpledialog.askstring', return_value='converted'), \
             patch('tkinter.messagebox.showinfo'):
            self.gui.export()
            self.wait()
        self.assertTrue((self.folder / 'converted' / 'MainData00.dat').is_file())
        self.app.show_library()
        self.assertIs(self.app.select_game('dw6_ps3'), editor)
        self.assertEqual(editor.changes['horse_0_speed'], 500)
        self.app.show_converter()
        self.assertIs(self.app.converter, self.gui)
        self.gui.source.set('changed-selection.dat')
        self.assertIsNone(self.gui.prepared)
        self.assertIn('disabled', self.gui.export_button.state())

    def test_background_errors_and_stale_review_never_enable_export(self):
        self.select_copies()
        self.gui.source.set(str(self.folder / 'missing.dat'))
        with patch('tkinter.messagebox.showerror') as error:
            self.gui.review()
            self.wait()
        error.assert_called_once()
        self.assertIsNone(self.gui.prepared)
        # A programmatic selection change during work invalidates its result.
        self.gui.source.set(str(self.folder / 'source' / 'save.dat'))
        self.gui.review()
        self.gui.template.set('different-template.dat')
        self.wait()
        self.assertIsNone(self.gui.prepared)
        self.assertIn('disabled', self.gui.export_button.state())

    def test_close_waits_for_active_operation(self):
        self.gui.busy = True
        with patch('tkinter.messagebox.showinfo') as info:
            self.app.close()
        info.assert_called_once()
        self.assertTrue(self.root.winfo_exists())
        self.gui.busy = False


class ConversionCliTests(unittest.TestCase):
    def test_list_dry_run_export_and_failure_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = fixtures.write_copy(folder / 'source', 'dw8xl')
            template = fixtures.write_copy(folder / 'template', 'dw8xl_vita')
            base = [sys.executable, '-m', 'koei_editor']
            listed = subprocess.run(base + ['--list-conversions'], capture_output=True, text=True, cwd=directory, timeout=30)
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertEqual(len(listed.stdout.splitlines()), len(conversion.ROUTES))
            command = base + ['--convert', 'dw8xl-to-dw8xl_vita', '--source', str(source), '--template', str(template)]
            result = subprocess.run(command + ['--dry-run'], capture_output=True, text=True, cwd=directory, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)['dry_run'])
            self.assertFalse(any(folder.rglob('*.json')))
            result = subprocess.run(command + ['--output-dir', str(folder / 'export')], capture_output=True, text=True, cwd=directory, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(json.loads(result.stdout)['game_load_verified'])
            for bad in (command, command + ['--output-dir', str(folder / 'export')],
                        base + ['--convert', 'unknown', '--source', str(source), '--template', str(template), '--dry-run'],
                        base + ['--list-conversions', '--self-test', 'a', 'b'],
                        base + ['--list-conversions', '--game', 'dw6_ps3'],
                        base + ['--list-conversions', '--source', str(source)]):
                failed = subprocess.run(bad, capture_output=True, text=True, cwd=directory, timeout=30)
                self.assertNotEqual(failed.returncode, 0)
                self.assertNotIn('Traceback', failed.stderr)
