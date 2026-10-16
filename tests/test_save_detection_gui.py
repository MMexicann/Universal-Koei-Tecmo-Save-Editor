"""Real Tk discovery/import workers preserve cancellation and callback boundaries."""
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.shared import save_detection as backend
from koei_editor.shared.save_detection_gui import SaveDetectionWorkspace
from koei_editor.shared.appearance import THEMES
from tests.test_save_detection import installation
from tests.test_verified_editors import synthetic_raw


class DetectionGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name).resolve()
        self.steam, self.documents, self.output = (self.folder / part for part in ('Steam', 'Documents', 'Output'))
        self.steam.mkdir(); self.documents.mkdir(); self.output.mkdir()
        installation(self.steam, 278080)
        profile = next(p for p in backend.PROFILES if p.game_id == 'dw8xl')
        self.source = self.documents.joinpath(*profile.documents_folder) / 'save.dat'
        self.source.parent.mkdir(parents=True)
        self.original = synthetic_raw('dw8xl'); self.source.write_bytes(self.original)
        self.opened = []
        self.workspace = SaveDetectionWorkspace(self.root, self.root,
            on_open=lambda game_id, path: self.opened.append((game_id, Path(path))) or False)
        self.workspace.frame.pack(fill='both', expand=True)
        self.addCleanup(self.workspace.close)
        self.workspace.steam_root.set(str(self.steam))

    def wait(self):
        until = time.monotonic() + 10
        while self.workspace.busy and time.monotonic() < until:
            self.root.update()
            time.sleep(.01)
        self.assertFalse(self.workspace.busy)

    def scan(self):
        with patch.object(backend, 'default_documents_roots', return_value=(self.documents,)):
            self.workspace.scan()
            self.assertFalse(self.workspace.has_pending_work())
            self.wait()

    def test_scan_search_status_theme_and_explicit_import_keep_original_untouched(self):
        self.scan()
        row, = self.workspace.table.get_children()
        self.workspace.table.selection_set(row); self.workspace.selection_changed()
        self.assertEqual(str(self.workspace.import_button.cget('state')), 'normal')
        self.assertFalse(self.opened)
        for theme in ('Dark', 'Light'):
            self.workspace.apply_theme(THEMES[theme])
        self.workspace.search.set('not found')
        self.assertFalse(self.workspace.table.get_children())
        self.workspace.search.set('dynasty warriors 8')
        self.assertEqual(len(self.workspace.table.get_children()), 1)
        self.workspace.table.selection_set(row); self.workspace.selection_changed()
        with patch('koei_editor.shared.save_detection_gui.filedialog.askdirectory', return_value=str(self.output)), patch(
                'koei_editor.shared.save_detection_gui.messagebox.showerror') as errors:
            self.workspace.import_selected()
            self.assertTrue(self.workspace.has_pending_work())
            self.wait()
            errors.assert_not_called()
        game_id, copied = self.opened[0]
        self.assertEqual(game_id, 'dw8xl')
        self.assertTrue(copied.is_relative_to(self.output))
        self.assertEqual(copied.read_bytes(), self.original)
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertIn('current editor session was preserved', self.workspace.status.get())

    def test_cancelled_and_invalidated_workers_cannot_open_or_publish_stale_scan(self):
        entered, release = threading.Event(), threading.Event()
        def delayed(cancel):
            entered.set(); release.wait(5)
            return backend.DetectionScan((), (), 'cancelled', 0, 0)
        self.workspace._start('scan', delayed)
        self.assertTrue(entered.wait(2))
        self.workspace.steam_root.set(str(self.folder / 'OtherSteam'))
        release.set(); self.wait()
        self.assertIsNone(self.workspace.prepared)
        self.assertFalse(self.opened)
        self.assertIn('cancelled', self.workspace.status.get())
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_missing_or_rejected_selection_cannot_start_import(self):
        self.workspace.import_selected()
        self.assertFalse(self.workspace.busy)
        entry = backend.DetectionEntry('dw8xl', 278080, 'DW8', 'rejected', 'Unsupported revision')
        self.workspace.prepared = backend.DetectionScan((entry,), (), 'complete', 0, 0)
        self.workspace.refresh()
        self.workspace.table.selection_set('0'); self.workspace.selection_changed()
        with patch('koei_editor.shared.save_detection_gui.filedialog.askdirectory') as choose:
            self.workspace.import_selected()
        choose.assert_not_called()
        self.assertFalse(self.opened)


if __name__ == '__main__':
    unittest.main()
