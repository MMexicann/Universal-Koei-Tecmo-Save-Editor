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

    def test_dw6_scope_is_visible_before_review_and_ctrl_f_retains_converter(self):
        source = fixtures.write_copy(self.folder / 'dw6-source', 'dw6')
        template = fixtures.write_copy(self.folder / 'dw6-template', 'dw6_ps3')
        self.gui.route.set(conversion.get_route('dw6-to-dw6_ps3').label)
        self.gui.source.set(str(source))
        self.gui.template.set(str(template))
        self.assertIn('destination story', self.gui.scope.get())
        self.root.update_idletasks()
        platform = self.app.platform_choice.get()
        self.app.focus_library_search()
        self.assertEqual(self.gui.frame.winfo_manager(), 'pack')
        self.assertEqual(self.app.platform_choice.get(), platform)
        self.gui.review()
        self.wait()
        self.assertIn('partial progress', self.gui.preview.get('1.0', 'end'))
        self.assertEqual(self.gui.prepared.gameplay_bytes, 7368)

    def test_named_ps3_unlock_workflow_stays_separate_from_stats_and_story(self):
        editor = self.app.select_game('dw6_ps3')
        source = self.folder / 'APP.BIN'
        source.write_bytes(dw6.fixture())
        dw6.context(self.folder)
        with patch('tkinter.filedialog.askopenfilename', return_value=str(source)):
            editor.open()
        editor.unlock_all()
        self.assertEqual(len(editor.changes), 21)
        self.assertTrue(all(key.endswith('_unlocked') for key in editor.changes))
        self.assertIn('Xiahou Dun', str(editor.backend.inspection_rows(editor.document)))
        self.app.show_converter()
        self.assertIs(self.app.select_game('dw6_ps3'), editor)
        self.assertEqual(len(editor.changes), 21)

    def test_progress_scope_and_japanese_destination_are_reviewable_before_export(self):
        source = fixtures.write_copy(self.folder / 'progress-source', 'dw6')
        template = fixtures.write_copy(self.folder / 'progress-template', 'dw6_ps3_jp')
        route = conversion.get_route('dw6-to-dw6_ps3_jp-progress')
        self.gui.route.set(route.label)
        self.gui.source.set(str(source))
        self.gui.template.set(str(template))
        self.assertIn('45 persistent stage', self.gui.scope.get())
        self.assertIn('17 Musou', self.gui.scope.get())
        self.gui.review()
        self.wait()
        self.assertEqual(self.gui.prepared.gameplay_bytes, 8336)
        self.assertIn('Stage review:', self.gui.preview.get('1.0', 'end'))
        self.assertIn('Musou history review:', self.gui.preview.get('1.0', 'end'))

    def test_route_search_covers_region_scope_and_ids_without_silent_reselection(self):
        self.select_copies()
        self.gui.review()
        self.wait()
        reviewed = self.gui.prepared
        selected = self.gui.route.get()
        self.gui.route_search.set('dw8 vita')
        self.assertIn(selected, self.gui.route_selector.cget('values'))
        self.assertIs(self.gui.prepared, reviewed)
        self.gui.route_search.set('BLES00215 campaigns')
        labels = self.gui.route_selector.cget('values')
        expected = {route.label for route in conversion.ROUTES if route.variant == 'campaigns'
                    and 'dw6_ps3_eu' in (route.source_id, route.target_id)}
        self.assertEqual(set(labels), expected)
        self.assertEqual(self.gui.route.get(), '')
        self.assertIsNone(self.gui.prepared)
        self.assertIn('disabled', self.gui.export_button.state())
        self.assertIn('disabled', self.gui.review_button.state())
        # The paths are retained for deliberate review after choosing a route.
        self.assertTrue(self.gui.source.get())
        self.gui.route.set(conversion.get_route('dw6-to-dw6_ps3_eu-campaigns').label)
        self.assertIn('20 Musou run slots', self.gui.scope.get())
        self.gui.route_search.set('no-such-game')
        self.assertEqual(tuple(self.gui.route_selector.cget('values')), ())
        self.assertIn('disabled', self.gui.route_selector.state())
        with patch('tkinter.messagebox.showerror') as error, patch('tkinter.filedialog.askopenfilename') as browse:
            self.gui.review()
            self.gui.browse('source')
        self.assertEqual(error.call_count, 2)
        browse.assert_not_called()
        self.gui.route_search.set('')
        self.assertEqual(len(self.gui.route_selector.cget('values')), len(conversion.ROUTES))
        self.assertIn('readonly', self.gui.route_selector.state())
        self.assertEqual(self.gui.route.get(), '')
        with patch.object(self.gui.search_entry, 'focus_set') as focus:
            self.assertEqual(self.app.focus_library_search(), 'break')
        focus.assert_called_once()

    def test_european_campaign_scope_review_and_filter_change_during_worker(self):
        source = fixtures.write_copy(self.folder / 'campaign-source', 'dw6')
        template = fixtures.write_copy(self.folder / 'campaign-template', 'dw6_ps3_eu')
        self.gui.route_search.set('BLES00215 campaigns')
        self.gui.route.set(conversion.get_route('dw6-to-dw6_ps3_eu-campaigns').label)
        self.gui.source.set(str(source))
        self.gui.template.set(str(template))
        self.gui.review()
        self.assertIn('disabled', self.gui.search_entry.state())
        self.wait()
        self.assertEqual(self.gui.prepared.gameplay_bytes, 10976)
        self.assertIn('Musou slot review:', self.gui.preview.get('1.0', 'end'))
        self.gui.review()
        self.gui.route_search.set('Persona')
        self.wait()
        self.assertIsNone(self.gui.prepared)
        self.assertIn('disabled', self.gui.export_button.state())

    def test_gallery_challenge_scope_review_is_separate_from_campaign_slots(self):
        source = fixtures.write_copy(self.folder / 'records-source', 'dw6')
        template = fixtures.write_copy(self.folder / 'records-template', 'dw6_ps3_jp', 1)
        self.gui.route_search.set('Japanese gallery challenges')
        route = conversion.get_route('dw6-to-dw6_ps3_jp-records')
        self.assertIn(route.label, self.gui.route_selector.cget('values'))
        self.gui.route.set(route.label)
        self.gui.source.set(str(source))
        self.gui.template.set(str(template))
        self.assertIn('five challenge boards', self.gui.scope.get())
        self.gui.review()
        self.wait()
        self.assertEqual(self.gui.prepared.gameplay_bytes, 11203)
        preview = self.gui.preview.get('1.0', 'end')
        self.assertIn('Gallery review:', preview)
        self.assertIn('Challenge review:', preview)
        self.assertIn('reserved bits remain from the destination', preview)
        self.gui.route_search.set('')
        self.gui.route.set(conversion.get_route('dw6-to-dw6_ps3_jp-campaigns').label)
        self.assertIsNone(self.gui.prepared)
        self.assertIn('disabled', self.gui.export_button.state())
        self.gui.review()
        self.wait()
        self.assertEqual(self.gui.prepared.gameplay_bytes, 10976)
        self.assertNotIn('Gallery review:', self.gui.preview.get('1.0', 'end'))

    def test_dw7_xl_one_way_scope_search_review_and_pc_export(self):
        from koei_editor.games.dw7xl import conversion as transfer
        from koei_editor.games.dw7xl import dw7xl_parser as pc
        source = fixtures.write_copy(self.folder / 'xl-source', 'dw7xl_ps3')
        template = fixtures.write_copy(self.folder / 'xl-template', 'dw7xl', 1)
        original_source, original_template = source.read_bytes(), template.read_bytes()
        self.gui.route_search.set('DW7 BLES01496')
        route = conversion.get_route('dw7xl_ps3-to-dw7xl')
        self.assertEqual(tuple(self.gui.route_selector.cget('values')), (route.label,))
        self.gui.route.set(route.label)
        self.gui.source.set(str(source))
        self.gui.template.set(str(template))
        self.assertIn('Definitive Edition PC', self.gui.scope.get())
        self.gui.review()
        self.wait()
        reviewed = self.gui.prepared
        self.assertIsNotNone(reviewed)
        preview = self.gui.preview.get('1.0', 'end')
        self.assertIn('Officer review:', preview)
        self.assertIn('Weapon review:', preview)
        self.assertIn('Challenge review:', preview)
        self.assertIn('re-saving remain unverified', preview)
        with patch('tkinter.filedialog.askdirectory', return_value=str(self.folder)), \
             patch('tkinter.simpledialog.askstring', return_value='xl-converted'), \
             patch('tkinter.messagebox.showinfo'):
            self.gui.export()
            self.wait()
        output = self.folder / 'xl-converted'
        reopened = pc.read_save(output / 'save.dat')
        self.assertEqual(transfer.gameplay(reopened), transfer.gameplay(reviewed.source.document))
        self.assertFalse((output / 'PARAM.SFO').exists())
        self.assertEqual(source.read_bytes(), original_source)
        self.assertEqual(template.read_bytes(), original_template)
        self.assertFalse(json.loads((output / 'conversion.json').read_text())['game_load_verified'])


class ConversionCliTests(unittest.TestCase):
    def test_dw7_xl_cli_export_and_unqualified_reverse_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = fixtures.write_copy(folder / 'source', 'dw7xl_ps3')
            template = fixtures.write_copy(folder / 'template', 'dw7xl', 1)
            command = [sys.executable, '-m', 'koei_editor', '--convert', 'dw7xl_ps3-to-dw7xl',
                       '--source', str(source), '--template', str(template)]
            dry = subprocess.run(command + ['--dry-run'], capture_output=True, text=True,
                                 cwd=directory, timeout=30)
            self.assertEqual(dry.returncode, 0, dry.stderr)
            self.assertTrue(json.loads(dry.stdout)['dry_run'])
            self.assertFalse(any(folder.rglob('UniversalEditorBackups')))
            result = subprocess.run(command + ['--output-dir', str(folder / 'output')],
                                    capture_output=True, text=True, cwd=directory, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads(result.stdout)
            self.assertEqual(receipt['route'], 'dw7xl_ps3-to-dw7xl')
            self.assertEqual(receipt['output_file'], 'save.dat')
            self.assertFalse(receipt['game_load_verified'])
            self.assertTrue((folder / 'output' / 'save.dat').exists())
            command[4] = 'dw7xl-to-dw7xl_ps3'
            rejected = subprocess.run(command + ['--dry-run'], capture_output=True, text=True,
                                      cwd=directory, timeout=30)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertNotIn('Traceback', rejected.stderr)

    def test_list_dry_run_export_and_failure_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = fixtures.write_copy(folder / 'source', 'dw8xl')
            template = fixtures.write_copy(folder / 'template', 'dw8xl_vita')
            base = [sys.executable, '-m', 'koei_editor']
            listed = subprocess.run(base + ['--list-conversions'], capture_output=True, text=True, cwd=directory,
                                    env={**os.environ, 'PYTHONIOENCODING': 'ascii'}, timeout=30)
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertEqual(len(listed.stdout.splitlines()), len(conversion.ROUTES))
            self.assertTrue(listed.stdout.isascii())
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
