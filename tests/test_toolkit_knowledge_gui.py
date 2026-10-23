"""Reference provenance, real snapshot comparisons, and desktop workflows."""

import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.shared.appearance import THEMES
from koei_editor.shared.game_compatibility import CompatibilityInputError, SNAPSHOT_SCHEMA_ID
from koei_editor.shared.game_data_encyclopedia import load_game_data_encyclopedia
from koei_editor.shared.toolkit_knowledge_gui import (
    EncyclopediaWorkspace, PatchCompatibilityWorkspace, analyze_snapshot_files,
    encyclopedia_details, export_compatibility_report, filter_encyclopedia,
)


def snapshot(version, payload):
    return {
        'schema_id': SNAPSHOT_SCHEMA_ID, 'schema_version': 1,
        'game_id': 'dw8xl', 'platform_id': 'windows',
        'version': {'value': version, 'source': 'controlled fixture'},
        'files': [{'relative_path': 'data/example.bin', 'size_bytes': len(payload),
                   'sha256': hashlib.sha256(payload).hexdigest()}],
        'archives': [], 'formats': [],
    }


class KnowledgeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = load_game_data_encyclopedia()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)

    def inputs(self):
        before, after = self.folder / 'before.json', self.folder / 'after.json'
        before.write_text(json.dumps(snapshot('1.0', b'before')), encoding='utf-8')
        after.write_text(json.dumps(snapshot('1.1', b'after')), encoding='utf-8')
        return before, after

    def test_reference_search_combines_exact_game_kind_and_all_query_words(self):
        original = copy.deepcopy(self.dataset)
        rows = filter_encyclopedia(self.dataset, 'BYLETH female', 'three_hopes', 'character')
        self.assertEqual([row['name'] for row in rows], ['Byleth (female)'])
        self.assertEqual(filter_encyclopedia(self.dataset, 'Byleth', 'hyrule_warriors'), ())
        self.assertEqual(filter_encyclopedia(self.dataset, 'Byleth', kind='weapon'), ())
        self.assertEqual(self.dataset, original)

    def test_reference_native_id_search_keeps_edition_context(self):
        row = next(row for row in self.dataset['entities'] if row['id'] == 'three_hopes:character:002')
        found = filter_encyclopedia(self.dataset, '2 Edelgard Switch', 'three_hopes', 'character')
        self.assertEqual(found, (row,))

    def test_reference_details_include_all_fact_and_profile_sources(self):
        row = next(row for row in self.dataset['entities'] if 'summary' in row)
        details = encyclopedia_details(self.dataset, row['id'])
        self.assertIn(row['edition'], details)
        self.assertIn(row['summary'], details)
        games = {game['id']: game for game in self.dataset['games']}
        source_ids = set(row['field_sources'].values()) | {games[row['game_id']]['profile_source_id']}
        for source in self.dataset['sources']:
            if source['id'] in source_ids:
                for field in ('uri', 'license_uri', 'attribution', 'scope'):
                    self.assertIn(source[field], details)
        self.assertIn(self.dataset['dataset_license_note'], details)
        with self.assertRaises(ValueError):
            encyclopedia_details(self.dataset, 'missing:entity')

    def test_real_file_comparison_and_exports_preserve_inputs(self):
        before, after = self.inputs()
        original = before.read_bytes(), after.read_bytes()
        report = analyze_snapshot_files(before, after)
        self.assertTrue(report['has_changes'])
        self.assertEqual(report['overall_status'], 'unknown')
        self.assertEqual(len(report['file_changes']['modified']), 1)
        output = export_compatibility_report(report, self.folder / 'report.json')
        self.assertEqual(json.loads(output.read_text(encoding='utf-8')), report)
        markdown = export_compatibility_report(report, self.folder / 'report.md').read_text(encoding='utf-8')
        self.assertIn('example.bin', markdown)
        self.assertIn(report['impacts']['interpretation'], markdown)
        self.assertNotIn(str(self.folder), markdown)
        self.assertEqual((before.read_bytes(), after.read_bytes()), original)

    def test_invalid_requirements_and_cross_game_snapshots_are_rejected(self):
        before, after = self.inputs()
        required = self.folder / 'requirements.json'
        required.write_text('{"schema_version": 1}', encoding='utf-8')
        with self.assertRaises(CompatibilityInputError):
            analyze_snapshot_files(before, after, required)
        foreign = snapshot('1.1', b'after')
        foreign['game_id'] = 'other-game'
        after.write_text(json.dumps(foreign), encoding='utf-8')
        with self.assertRaisesRegex(CompatibilityInputError, 'same game_id'):
            analyze_snapshot_files(before, after)

    def test_duplicate_keys_and_invalid_utf8_fail_without_outputs(self):
        before, after = self.inputs()
        for invalid in (b'{"schema_version":1,"schema_version":1}', b'\xff'):
            before.write_bytes(invalid)
            with self.assertRaises(CompatibilityInputError):
                analyze_snapshot_files(before, after)
        self.assertEqual(set(self.folder.iterdir()), {before, after})

    def test_report_exports_never_overwrite_input_or_existing_output(self):
        before, after = self.inputs()
        report = analyze_snapshot_files(before, after)
        original = before.read_bytes()
        with self.assertRaises(FileExistsError):
            export_compatibility_report(report, before)
        self.assertEqual(before.read_bytes(), original)
        output = self.folder / 'existing.md'
        output.write_bytes(b'keep existing report')
        with self.assertRaises(FileExistsError):
            export_compatibility_report(report, output)
        self.assertEqual(output.read_bytes(), b'keep existing report')
        with self.assertRaises(ValueError):
            export_compatibility_report(report, self.folder / 'report.txt')

    def test_report_export_rejects_hardlink_alias_of_input(self):
        before, after = self.inputs()
        report = analyze_snapshot_files(before, after)
        alias = self.folder / 'alias.json'
        os.link(before, alias)
        original = before.read_bytes()
        with self.assertRaises(FileExistsError):
            export_compatibility_report(report, alias)
        self.assertEqual(before.read_bytes(), original)


class KnowledgeWorkspaceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.root.destroy)
        self.root.geometry('900x720')

    def workspace(self, kind):
        workspace = kind(self.root, self.root)
        workspace.frame.pack(fill='both', expand=True)
        self.addCleanup(workspace.close)
        self.root.update()
        return workspace

    def inputs(self, workspace):
        for key, version, payload in (('baseline', '1', b'a'), ('candidate', '2', b'b')):
            path = self.folder / (key + '.json')
            path.write_text(json.dumps(snapshot(version, payload)), encoding='utf-8')
            workspace.paths[key].set(str(path))

    def finish(self, workspace):
        deadline = time.monotonic() + 10
        while workspace.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(.01)
        self.assertFalse(workspace.busy, 'comparison worker did not finish')

    def test_encyclopedia_search_selection_and_language_preserve_provenance(self):
        workspace = self.workspace(EncyclopediaWorkspace)
        workspace.search.set('Edelgard')
        self.root.update()
        self.assertEqual(len(workspace.rows), 1)
        entity_id = workspace.rows[0]['id']
        workspace.table.selection_set(entity_id)
        workspace._selected()
        details = workspace.details.get('1.0', 'end')
        self.assertIn('MIT', details)
        self.assertIn('Switch', details)
        workspace.set_language('de')
        workspace.apply_theme(THEMES['Dark'])
        workspace.set_text_size(12, 'Helvetica')
        self.assertEqual(workspace.table.selection(), (entity_id,))
        self.assertIn('Datensätze', workspace.status.get())
        self.assertEqual(workspace.details.get('1.0', 'end'), details)

    def test_missing_inputs_do_not_start_worker_or_enable_export(self):
        workspace = self.workspace(PatchCompatibilityWorkspace)
        workspace.compare()
        self.assertFalse(workspace.busy)
        self.assertIsNone(workspace.report)
        self.assertIn('both', workspace.status.get())
        self.assertEqual(str(workspace.json_button['state']), 'disabled')

    def test_actual_comparison_and_dialog_export_then_input_invalidation(self):
        workspace = self.workspace(PatchCompatibilityWorkspace)
        self.inputs(workspace)
        workspace.compare()
        self.finish(workspace)
        self.assertTrue(workspace.report['has_changes'])
        self.assertIn('example.bin', workspace.preview.get('1.0', 'end'))
        output = self.folder / 'comparison.json'
        with patch('koei_editor.shared.toolkit_knowledge_gui.filedialog.asksaveasfilename', return_value=str(output)):
            workspace.export('.json')
        self.assertEqual(json.loads(output.read_text(encoding='utf-8')), workspace.report)
        workspace.paths['requirements'].set(str(self.folder / 'new.json'))
        self.assertIsNone(workspace.report)
        self.assertEqual(str(workspace.json_button['state']), 'disabled')
        self.assertNotIn('example.bin', workspace.preview.get('1.0', 'end'))

    def test_invalid_new_inputs_cannot_export_prior_success(self):
        workspace = self.workspace(PatchCompatibilityWorkspace)
        self.inputs(workspace)
        workspace.compare()
        self.finish(workspace)
        self.assertIsNotNone(workspace.report)
        invalid = self.folder / 'bad.json'
        invalid.write_text('{bad json}', encoding='utf-8')
        workspace.paths['candidate'].set(str(invalid))
        workspace.compare()
        self.finish(workspace)
        self.assertIsNone(workspace.report)
        self.assertEqual(str(workspace.markdown_button['state']), 'disabled')
        self.assertIn('Invalid JSON', workspace.preview.get('1.0', 'end'))

    def test_closed_workspace_cancels_polling_without_destroying_inputs(self):
        workspace = self.workspace(PatchCompatibilityWorkspace)
        self.inputs(workspace)
        entered, release = threading.Event(), threading.Event()
        workers = []
        thread_type = threading.Thread
        compare_inputs = analyze_snapshot_files

        def capture_thread(*args, **kwargs):
            worker = thread_type(*args, **kwargs)
            workers.append(worker)
            return worker

        def held_input(*args):
            # Keep an actual input handle open while close runs. Windows must
            # not race TemporaryDirectory cleanup against this deliberate read.
            with (self.folder / 'candidate.json').open('rb'):
                entered.set()
                if not release.wait(10):
                    raise AssertionError('The test did not release its comparison worker.')
            return compare_inputs(*args)

        def release_and_join():
            release.set()
            for worker in workers:
                worker.join(timeout=10)
                self.assertFalse(worker.is_alive(), 'Comparison worker did not release input handles.')

        self.addCleanup(release_and_join)
        with patch('koei_editor.shared.toolkit_knowledge_gui.threading.Thread', side_effect=capture_thread), \
                patch('koei_editor.shared.toolkit_knowledge_gui.analyze_snapshot_files', side_effect=held_input):
            workspace.compare()
            self.assertTrue(entered.wait(10), 'Comparison worker did not open the input.')
            workspace.close()
            self.assertTrue(workers[0].is_alive(), 'Closing must not join a blocked read on the UI thread.')
            self.assertIsNone(workspace._poll_id)
            self.root.update()
            self.assertEqual(json.loads((self.folder / 'baseline.json').read_text())['version']['value'], '1')
            release_and_join()
            _revision, report, _markdown, error = workspace._results.get_nowait()
            self.assertIsNone(error)
            self.assertTrue(report['has_changes'])
            self.assertEqual(json.loads((self.folder / 'candidate.json').read_text())['version']['value'], '2')


if __name__ == '__main__':
    unittest.main()
