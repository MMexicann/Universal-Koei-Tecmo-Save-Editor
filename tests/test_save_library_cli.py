"""Headless, read-only Save Library CLI summaries and explicit exit states."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from koei_editor import application
from koei_editor.games.wo1_pc import wo1_parser
from koei_editor.shared import save_library
from tests.test_wo1_pc_format import procedural_raw


class SaveLibraryCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name) / 'private-owner-secret'
        self.folder.mkdir()

    def copy(self, name='private-slot-one.dat', raw=None):
        path = self.folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(procedural_raw() if raw is None else raw)
        return path

    def invoke(self, *arguments):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(sys, 'argv', ['koei-editor', *map(str, arguments)]), \
                patch.object(application.tk, 'Tk', side_effect=AssertionError('Headless command created a Tk root')), \
                redirect_stdout(output), redirect_stderr(errors):
            try:
                application.main()
            except SystemExit as error:
                code = error.code
            else:
                code = 0
        return code, output.getvalue(), errors.getvalue()

    def test_flat_and_recursive_qualification_are_read_only_and_path_free(self):
        first = self.copy()
        second = self.copy('nested/private-slot-two.dat')
        original = {str(path.relative_to(self.folder)): path.read_bytes() for path in (first, second)}
        with patch.object(wo1_parser, 'save_as', side_effect=AssertionError('A scan wrote gameplay')), \
                patch.object(wo1_parser, 'backup', side_effect=AssertionError('A scan created a backup')):
            code, output, errors = self.invoke('--scan-saves', self.folder, '--game', 'wo1')
            self.assertEqual(code, 0, errors)
            flat = json.loads(output)
            self.assertFalse(flat['recursive'])
            self.assertEqual(flat['candidate_files'], 1)
            self.assertEqual(flat['statuses']['qualified'], 1)
            code, output, errors = self.invoke('--game', 'wo1', '--scan-saves', self.folder, '--recursive')
            self.assertEqual(code, 0, errors)
            result = json.loads(output)
            self.assertTrue(result['read_only'])
            self.assertTrue(result['historical_scan'])
            self.assertTrue(result['recursive'])
            self.assertEqual(result['candidate_files'], 2)
            self.assertEqual(result['statuses']['qualified'], 2)
            self.assertEqual(result['identical_gameplay_file_groups'], 1)
            self.assertEqual(result['files_in_identical_gameplay_groups'], 2)
        self.assertEqual(errors, '')
        for private in (str(self.folder), 'private-owner-secret', first.name, second.name, 'sha256'):
            self.assertNotIn(private, output)
        self.assertEqual({str(path.relative_to(self.folder)): path.read_bytes()
                          for path in self.folder.rglob('*') if path.is_file()}, original)

    def test_completed_mixed_results_and_no_qualified_copies_exit_one(self):
        first = self.copy()
        broken = self.copy('private-damaged.dat', b'foreign bytes')
        code, output, errors = self.invoke('--scan-saves', self.folder, '--game', 'wo1')
        self.assertEqual((code, errors), (1, ''))
        result = json.loads(output)
        self.assertEqual(result['stop_reason'], 'complete')
        self.assertEqual((result['statuses']['qualified'], result['statuses']['rejected']), (1, 1))
        # An explicitly different profile must reject, never probe the WO1 reader.
        with patch.object(wo1_parser, 'read_save', side_effect=AssertionError('Wrong-profile fallback')):
            code, output, errors = self.invoke('--scan-saves', self.folder, '--game', 'sw2')
        self.assertEqual((code, errors), (1, ''))
        self.assertEqual(json.loads(output)['statuses']['qualified'], 0)
        self.assertEqual(first.read_bytes(), procedural_raw())
        self.assertEqual(broken.read_bytes(), b'foreign bytes')
        empty = self.folder / 'empty'
        empty.mkdir()
        code, output, errors = self.invoke('--scan-saves', empty, '--game', 'wo1')
        self.assertEqual((code, errors), (1, ''))
        self.assertEqual(json.loads(output)['candidate_files'], 0)

    def test_real_file_limit_emits_partial_json_and_exit_three(self):
        # Tiny rejected candidates exercise the actual 500-file bound without
        # retaining game data or using fake result objects/raised scan limits.
        for index in range(501):
            self.copy(f'candidate-{index:03}.dat', b'x')
        code, output, errors = self.invoke('--scan-saves', self.folder, '--game', 'wo1')
        self.assertEqual((code, errors), (3, ''))
        result = json.loads(output)
        self.assertEqual((result['stop_reason'], result['candidate_files']), ('file_limit', 500))
        self.assertEqual(result['statuses']['rejected'], 500)
        self.assertEqual(len(tuple(self.folder.iterdir())), 501)
        self.assertNotIn(str(self.folder), output)

    def test_invocation_rejects_mixed_actions_and_unsupported_profiles_before_scanning(self):
        prefix = ['--scan-saves', self.folder, '--game', 'wo1']
        cases = [
            ['--scan-saves', self.folder], ['--scan-saves', '', '--game', 'wo1'],
            ['--scan-saves', self.folder, '--game', 'dw3'],
            ['--scan-saves', self.folder, '--game', 'unknown-profile'],
            ['--recursive'], ['--list-games', '--recursive'],
            prefix + ['--smoke-test'], prefix + ['--list-games'],
            prefix + ['--dry-run'], prefix + ['--source', ''],
            prefix + ['--template', ''], prefix + ['--output-dir', ''],
            prefix + ['--batch-report', ''], prefix + ['--comparison-report', ''],
            prefix + ['--compare', 'a', 'b'], prefix + ['--self-test', 'a', 'b'],
            prefix + ['--compatibility-test', 'a', 'b'],
            prefix + ['--convert', 'dw6-to-dw6_ps3'], prefix + ['--list-conversions'],
            prefix + ['--batch-convert', 'a'],
        ]
        with patch.object(save_library, 'scan', side_effect=AssertionError('Invalid invocation started a scan')):
            for arguments in cases:
                with self.subTest(arguments=arguments):
                    code, output, errors = self.invoke(*arguments)
                    self.assertEqual(code, 2)
                    self.assertEqual(output, '')
                    self.assertIn('error:', errors)
                    self.assertNotIn('private-owner-secret', errors)

    def test_operational_errors_do_not_expose_local_paths_or_exception_messages(self):
        missing = self.folder / 'private-missing-copy-folder'
        code, output, errors = self.invoke('--scan-saves', missing, '--game', 'wo1')
        self.assertEqual((code, output), (1, ''))
        self.assertIn('Save Library scan failed', errors)
        self.assertNotIn(str(missing), errors)
        for error in (OSError('PRIVATE FILE PATH'), ValueError('PRIVATE CONTEXT'), TypeError('PRIVATE FIELD')):
            with patch.object(save_library, 'scan', side_effect=error):
                code, output, errors = self.invoke('--scan-saves', self.folder, '--game', 'wo1')
            self.assertEqual((code, output), (1, ''))
            self.assertNotIn('PRIVATE', errors)

    def test_installed_module_runs_without_a_display_from_another_working_directory(self):
        source = self.copy()
        env = dict(os.environ, DISPLAY='')
        process = subprocess.run([sys.executable, '-m', 'koei_editor', '--scan-saves', str(self.folder),
                                  '--game', 'wo1'], cwd=self.folder, env=env,
                                 capture_output=True, text=True, timeout=30)
        self.assertEqual(process.returncode, 0, process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual((report['game_id'], report['statuses']['qualified']), ('wo1', 1))
        self.assertNotIn(str(self.folder), process.stdout + process.stderr)
        self.assertEqual(source.read_bytes(), procedural_raw())
        remaining = tuple(self.folder.iterdir())
        self.assertEqual(len(remaining), 1)
        self.assertTrue(remaining[0].samefile(source))

    def test_existing_read_only_lists_keep_their_independent_routing(self):
        with patch.object(save_library, 'scan', side_effect=AssertionError('Legacy command started a library scan')):
            for options, expected in ((['--list-games'], 'wo1:'), (['--list-conversions'], 'dw6-to-dw6_ps3:')):
                code, output, errors = self.invoke(*options)
                self.assertEqual((code, errors), (0, ''))
                self.assertIn(expected, output)
