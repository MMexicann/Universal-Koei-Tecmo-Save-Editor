"""Read-only candidate imports never become registered editors or write files."""
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.game_registry import get_game
from koei_editor.research import imports
from koei_editor.research.dk4pk_pc import inspector as dk4
from tests.test_expansion_candidates import vita_fixture, vita_metadata, gundam_fixture
from tests.test_ps3_expansion import PS3ContextTests


def dk4_fixture():
    raw = bytearray((i * 17 + 9) % 256 for i in range(39682))
    raw[:16] = dk4.MAGIC
    raw[16:20] = raw[28:32] = bytes(4)
    raw[20:24] = len(raw).to_bytes(4, 'little')
    return bytes(raw)


def write_candidate(folder, key):
    folder.mkdir(parents=True, exist_ok=True)
    profile = imports.PROFILES[key]
    path = folder / profile.filename
    if key == 'dk4pk_pc':
        path.write_bytes(dk4_fixture())
    elif key == 'gundam2_ps3':
        path.write_bytes(gundam_fixture())
        path.with_name('PARAM.SFO').write_bytes(PS3ContextTests.metadata('BLUS30288-00'))
    else:
        native = imports.vita.PROFILES[key]
        path.write_bytes(vita_fixture(native))
        metadata = folder / 'sce_sys' / 'param.sfo'
        metadata.parent.mkdir()
        metadata.write_bytes(vita_metadata(native.title_id))
    return path


class ResearchImportTests(unittest.TestCase):
    def test_all_candidates_require_explicit_identity_and_preserve_complete_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for key, profile in imports.PROFILES.items():
                with self.subTest(key=key):
                    source = write_candidate(root / key, key)
                    originals = {p: p.read_bytes() for p in source.parent.rglob('*') if p.is_file()}
                    result = imports.inspect_copy(key, source)
                    report = json.loads(result.report_json)
                    self.assertEqual(result.profile_id, key)
                    self.assertEqual(result.size_bytes, source.stat().st_size)
                    self.assertTrue(report['read_only'])
                    self.assertFalse(report['registered_editor'])
                    self.assertFalse(report['game_load_verified'])
                    self.assertEqual(report['research_warning'], imports.WARNING)
                    self.assertNotIn(str(root), result.report_json)
                    self.assertEqual(originals, {p: p.read_bytes() for p in source.parent.rglob('*') if p.is_file()})
                    with self.assertRaises(SaveError):
                        get_game(key)
                    for forbidden in ('save_as', 'stage', 'restore', 'serialize'):
                        self.assertFalse(hasattr(profile.backend, forbidden))
                    source.write_bytes(source.read_bytes() + b'\0')
                    with self.assertRaises(SaveError):
                        imports.inspect_copy(key, source)
            with self.assertRaises(SaveError):
                imports.inspect_copy('unknown', source)

    def test_dk4_header_only_rejects_foreign_profiles_without_checksum_claim(self):
        raw = dk4_fixture()
        report = dk4.inspect(dk4.decode(raw))
        self.assertFalse(report['native_checksum_established'])
        self.assertFalse(report['record_inspection_available'])
        for offset in (0, 16, 20, 28):
            broken = bytearray(raw)
            broken[offset] ^= 1
            with self.assertRaises(SaveError):
                dk4.decode(bytes(broken))
        with self.assertRaises(SaveError):
            dk4.decode(bytearray(raw))
        # Body changes cannot be called corrupt while its integrity is unknown.
        opaque = bytearray(raw)
        opaque[400] ^= 1
        self.assertFalse(dk4.inspect(dk4.decode(bytes(opaque)))['native_checksum_established'])
        for forged in (replace(dk4.decode(raw), raw=bytearray(raw)), None):
            with self.assertRaises(SaveError):
                dk4.inspect(forged)

    def test_context_and_gameplay_changes_during_inspection_never_return_stale_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = write_candidate(root / 'gundam', 'gundam2_ps3')
            native_inspect = imports.gundam.inspect
            def changed_context(document):
                report = native_inspect(document)
                meta = source.with_name('PARAM.SFO')
                meta.write_bytes(meta.read_bytes() + b'\0')
                return report
            with patch.object(imports.gundam, 'inspect', side_effect=changed_context), self.assertRaises(SaveError):
                imports.inspect_copy('gundam2_ps3', source)
            source = write_candidate(root / 'dk4', 'dk4pk_pc')
            native_inspect = dk4.inspect
            def changed_gameplay(document):
                report = native_inspect(document)
                data = bytearray(source.read_bytes())
                data[400] ^= 1
                source.write_bytes(data)
                return report
            with patch.object(dk4, 'inspect', side_effect=changed_gameplay), self.assertRaises(SaveError):
                imports.inspect_copy('dk4pk_pc', source)

    def test_source_cli_retains_existing_interface_and_lists_explicit_new_research_profile(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as temporary:
            source = write_candidate(Path(temporary), 'dk4pk_pc')
            result = subprocess.run([sys.executable, '-m', 'tools.inspect_candidate', '--profile',
                                     'dk4pk_pc', str(source)], capture_output=True, text=True,
                                    cwd=Path(__file__).resolve().parents[1], timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['profile'], 'dk4pk_pc')
            self.assertNotIn(str(source), result.stdout)

    @unittest.skipUnless(os.environ.get('DK4PK_NATIVE_DIR'), 'Original-PK native reference directory not supplied.')
    def test_private_complete_native_headers(self):
        paths = tuple(Path(os.environ['DK4PK_NATIVE_DIR']).glob('*.DK4'))
        self.assertTrue(paths)
        for path in paths:
            original = path.read_bytes()
            report = imports.inspect_copy('dk4pk_pc', path)
            self.assertFalse(json.loads(report.report_json)['native_checksum_established'])
            self.assertEqual(path.read_bytes(), original)


class ResearchImportGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        from koei_editor.application import Application
        self.app = Application(self.root, persist_preferences=False)
        self.gui = self.app.show_research_import()
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)

    def wait(self):
        deadline = time.monotonic() + 15
        while self.gui.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertFalse(self.gui.busy)
        self.root.update_idletasks()

    def select(self, key):
        source = write_candidate(self.folder / key, key)
        self.gui.profile.set(imports.PROFILES[key].label)
        self.gui.source.set(str(source))
        return source

    def test_inspection_and_clear_actions_remain_visible_in_a_small_window(self):
        from koei_editor.shared.research_import_gui import ResearchImportWorkspace
        window = tk.Toplevel(self.root)
        self.addCleanup(window.destroy)
        window.geometry('640x520')
        workspace = ResearchImportWorkspace(window, window)
        workspace.frame.pack(fill='both', expand=True)
        window.update()
        bottom = workspace.frame.winfo_rooty() + workspace.frame.winfo_height()
        for button in (workspace.inspect_button, workspace.clear_button):
            self.assertTrue(button.winfo_ismapped())
            self.assertLessEqual(button.winfo_rooty() + button.winfo_height(), bottom)

    def test_menu_palette_retained_state_themes_and_useful_readonly_records(self):
        self.assertIn('tool:research_import', {entry.id for entry in self.app.command_entries()})
        labels = []
        for key in ('editing_presets', 'transfer', 'research_lab', 'research_import'):
            index = self.app._editing_tools_menu_index(key)
            self.assertIsNotNone(index, f'Missing editing tool menu command: {key}')
            labels.append(self.app.editing_tools_menu.entrycget(index, 'label'))
        self.assertIn('Research Import', labels)
        self.select('gundam2_ps3')
        self.gui.inspect()
        self.wait()
        self.assertIsNotNone(self.gui.result)
        self.assertIn('Amuro Ray', self.gui.report.get('1.0', 'end'))
        self.assertIn(imports.WARNING, self.gui.report.get('1.0', 'end'))
        self.assertEqual(self.gui.report.cget('state'), 'disabled')
        self.app.apply_theme('Dark')
        self.app.show_library()
        self.assertIs(self.app.show_research_import(), self.gui)
        self.assertIsNotNone(self.gui.result)
        self.gui.search.set('unknown')
        self.assertIsNone(self.gui.result)
        self.assertEqual(self.gui.profile.get(), '')
        self.assertIn('disabled', self.gui.inspect_button.state())
        self.gui.search.set('')
        self.select('totori_plus_vita')
        self.gui.inspect()
        self.wait()
        self.assertIn('uninterpreted_tag_3_u32', self.gui.report.get('1.0', 'end'))
        self.gui.clear()
        self.assertIsNone(self.gui.result)
        self.assertEqual(self.gui.source.get(), '')

    def test_rejections_and_stale_worker_results_never_show_other_selection(self):
        source = self.select('dk4pk_pc')
        with patch('tkinter.messagebox.showerror') as error:
            source.write_bytes(b'foreign')
            self.gui.inspect()
            self.wait()
            error.assert_called_once()
        self.assertIsNone(self.gui.result)
        source.write_bytes(dk4_fixture())
        self.gui.inspect()
        self.gui.source.set('new selection')
        self.wait()
        self.assertIsNone(self.gui.result)
        self.assertEqual(self.gui.report.get('1.0', 'end').strip(), '')
