"""Real Tk research workflow, background workers and immutable source safety."""
import json
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.games.deception4_ps3 import parser
from koei_editor.shared.research_lab_gui import ResearchLabWorkspace
from tests.test_ps3_new_families import fixture
from tests import test_ps3_expansion


class ResearchLabGuiTests(unittest.TestCase):
    def setUp(self):
        try: self.root = tk.Tk()
        except tk.TclError as error: self.skipTest(str(error))
        self.addCleanup(self.root.destroy); self.root.withdraw()
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.first, self.second = self.folder / 'first.bin', self.folder / 'second.bin'
        self.first.write_bytes(fixture(parser))
        self.second.write_bytes(parser.serialize(parser.decode(fixture(parser)), {'warl': 32}))
        (self.folder / 'PARAM.SFO').write_bytes(test_ps3_expansion.PS3ContextTests.metadata('NPUB31442-GAMEDATA-10'))
        self.workspace = ResearchLabWorkspace(self.root, self.root)
        self.workspace.game.set(next(label for label, game in self.workspace._games.items() if game == parser.GAME_ID))
        self.workspace.first.set(str(self.first)); self.workspace.second.set(str(self.second))

    def finish(self):
        deadline = time.monotonic() + 10
        while self.workspace.busy and time.monotonic() < deadline:
            self.root.update(); time.sleep(0.01)
        self.assertFalse(self.workspace.busy, 'Research worker did not finish')

    def compare(self):
        self.workspace.compare(); self.finish()
        self.assertIsNotNone(self.workspace.prepared)

    def test_decoded_comparison_field_navigation_offset_and_candidate_search(self):
        self.compare(); workspace = self.workspace
        self.assertEqual(len(workspace.table.get_children()), 1)
        self.assertEqual(len(workspace.runs.get_children()), 1)
        workspace.table.selection_set('0'); workspace.jump_field(); self.finish()
        self.assertEqual(workspace.offset.get(), '0x20')
        self.assertTrue(workspace.hex_rows.get_children())
        self.assertTrue(workspace.interpretations.get_children())
        self.assertIn('XOR', workspace.offset_summary.get())
        workspace.observed_before.set('137'); workspace.observed_after.set('32')
        workspace.widths.set('4'); workspace.find_candidates(); self.finish()
        self.assertEqual(len(workspace.candidates.get_children()), 1)
        self.assertIn('unverified hypotheses', workspace.candidate_status.get())
        workspace.candidates.selection_set('0'); workspace.jump_candidate(); self.finish()
        self.assertEqual(workspace.last_offset, 0x20)

    def test_annotations_export_is_read_only_and_source_change_invalidates_research(self):
        self.compare(); workspace = self.workspace
        workspace.offset.set('0x20'); workspace.span.set('4'); workspace.inspect(); self.finish()
        workspace.note_title.set('Controlled observation'); workspace.note_observation.set('Currency changed')
        workspace.note_evidence.set('Repeat purchase'); workspace.action.set('One purchase')
        workspace.add_annotation(); self.assertEqual(len(workspace.annotations), 1)
        destination = self.folder / 'research.json'
        with patch('koei_editor.shared.research_lab_gui.filedialog.asksaveasfilename', return_value=str(destination)):
            workspace.export(); self.finish()
        result = json.loads(destination.read_text(encoding='utf-8'))
        self.assertEqual(result['annotations'][0]['observation'], 'Currency changed')
        self.assertEqual(result['controlled_action'], 'One purchase')
        self.assertEqual(self.first.read_bytes(), fixture(parser))
        workspace.notes.selection_set('0'); workspace.remove_annotation()
        self.assertFalse(workspace.annotations)
        self.first.write_bytes(b'changed'); destination = self.folder / 'stale.json'
        with patch('koei_editor.shared.research_lab_gui.messagebox.showerror'), \
             patch('koei_editor.shared.research_lab_gui.filedialog.asksaveasfilename', return_value=str(destination)):
            workspace.export(); self.finish()
        self.assertIsNone(workspace.prepared); self.assertFalse(destination.exists())
        self.assertFalse(workspace.runs.get_children())
        self.assertEqual(str(workspace.export_button['state']), 'disabled')

    def test_late_research_worker_cannot_attach_to_changed_copies(self):
        self.compare(); workspace = self.workspace
        entered, release = threading.Event(), threading.Event()
        from koei_editor.shared import research_lab
        original = research_lab.inspect_offset
        def delayed(*args):
            entered.set(); release.wait(5); return original(*args)
        with patch('koei_editor.shared.research_lab_gui.lab.inspect_offset', side_effect=delayed):
            workspace.inspect(); self.assertTrue(entered.wait(2))
            workspace.second.set(str(self.first)); release.set(); self.finish()
        self.assertIsNone(workspace.prepared); self.assertIsNone(workspace.last_offset)
        self.assertFalse(workspace.hex_rows.get_children())

    def test_routine_export_errors_preserve_annotations_action_and_comparison(self):
        self.compare(); workspace = self.workspace
        workspace.offset.set('0x20'); workspace.span.set('4')
        workspace.note_title.set('Keep observation'); workspace.note_observation.set('Repeat this action')
        workspace.action.set('One controlled action'); workspace.add_annotation()
        comparison, notes = workspace.prepared, workspace.annotations
        existing = self.folder / 'existing.json'; existing.write_text('unchanged', encoding='utf-8')
        for destination in (existing, self.folder / 'wrong.bin'):
            with patch('koei_editor.shared.research_lab_gui.messagebox.showerror'), \
                 patch('koei_editor.shared.research_lab_gui.filedialog.asksaveasfilename', return_value=str(destination)):
                workspace.export(); self.finish()
            self.assertIs(workspace.prepared, comparison)
            self.assertEqual(workspace.annotations, notes)
            self.assertEqual(workspace.action.get(), 'One controlled action')
            self.assertEqual(str(workspace.export_button['state']), 'normal')
        self.assertEqual(existing.read_text(encoding='utf-8'), 'unchanged')

    def test_invalid_annotation_and_query_feedback_do_not_change_save_bytes(self):
        self.compare(); workspace = self.workspace
        with patch('koei_editor.shared.research_lab_gui.messagebox.showerror') as errors:
            workspace.add_annotation(); self.assertTrue(errors.called)
            self.assertFalse(workspace.annotations)
            workspace.observed_before.set('137'); workspace.observed_after.set('137')
            workspace.find_candidates(); self.finish(); self.assertIsNotNone(workspace.prepared)
            self.assertEqual(str(workspace.export_button['state']), 'normal')
        self.assertEqual(self.first.read_bytes(), fixture(parser))

    def test_scrollable_workspace_and_last_byte_inspection_exports_exact_length(self):
        self.compare(); workspace = self.workspace
        workspace.frame.pack(fill='both', expand=True)
        self.root.deiconify(); self.root.geometry('1100x720'); self.root.update()
        bounds = workspace.canvas.bbox('all')
        self.assertGreater(bounds[3], workspace.canvas.winfo_height())
        workspace.canvas.yview_moveto(1); self.root.update()
        self.assertGreater(workspace.canvas.yview()[0], 0)
        self.assertTrue(workspace.focus_search()); self.root.update()
        self.assertEqual(workspace.canvas.yview()[0], 0)
        workspace.apply_theme({})
        last = len(workspace.prepared.left.payload) - 1
        workspace.offset.set(hex(last)); workspace.span.set('1'); workspace.inspect(); self.finish()
        destination = self.folder / 'last.json'
        with patch('koei_editor.shared.research_lab_gui.filedialog.asksaveasfilename', return_value=str(destination)):
            workspace.export(); self.finish()
        self.assertEqual(json.loads(destination.read_text(encoding='utf-8'))['offset_analysis']['length'], 1)
