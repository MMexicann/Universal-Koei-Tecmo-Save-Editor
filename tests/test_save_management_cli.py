"""Exercise save-management commands through the single installed application."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
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
from koei_editor.shared.save_vault import SaveVault
from tests.test_wo1_pc_format import procedural_raw


class SaveManagementCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.source = self.folder / 'private-slot.dat'
        self.raw = procedural_raw()
        self.source.write_bytes(self.raw)
        self.vault = self.folder / 'vault'

    def invoke(self, *arguments):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(sys, 'argv', ['koei-editor', *map(str, arguments)]), \
                patch.object(application.tk, 'Tk', side_effect=AssertionError('Headless command created Tk')), \
                redirect_stdout(output), redirect_stderr(errors):
            try:
                application.main()
            except SystemExit as error:
                code = error.code
            else:
                code = 0
        return code, output.getvalue(), errors.getvalue()

    def test_doctor_reference_digest_corruption_and_reports_are_read_only(self):
        before = self.source.stat()
        code, output, errors = self.invoke('--save-doctor', self.source, '--game', 'wo1',
                                           '--expected-sha256', hashlib.sha256(self.raw).hexdigest())
        self.assertEqual((code, errors), (0, ''))
        result = json.loads(output)
        self.assertEqual(result['status'], 'qualified')
        self.assertNotIn(str(self.folder), output)
        self.assertNotIn(self.source.name, output)
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertEqual(self.source.stat().st_mtime_ns, before.st_mtime_ns)
        code, output, errors = self.invoke('--save-doctor', self.source, '--game', 'wo1', '--expected-sha256', '0' * 64)
        self.assertEqual((code, errors), (1, ''))
        self.assertFalse(json.loads(output)['success'])
        self.source.write_bytes(self.raw[:-1])
        code, output, errors = self.invoke('--save-doctor', self.source, '--game', 'wo1')
        self.assertEqual((code, errors), (1, ''))
        self.assertFalse(json.loads(output)['success'])

    def test_discovery_headless_reports_omit_paths_and_do_not_touch_roots(self):
        steam = self.folder / 'Steam'
        steam.mkdir()
        code, output, errors = self.invoke('--discover-saves', '--steam-root', steam)
        self.assertEqual((code, errors), (0, ''))
        self.assertEqual(json.loads(output)['stop_reason'], 'complete')
        self.assertNotIn(str(self.folder), output)
        self.assertEqual(list(steam.iterdir()), [])

    def test_vault_create_snapshot_branch_compare_restore_and_leaf_management(self):
        code, output, errors = self.invoke('--vault-operation', 'create', '--vault-path', self.vault)
        self.assertEqual((code, errors), (0, ''))
        self.assertTrue(json.loads(output)['created'])
        code, output, errors = self.invoke('--vault-operation', 'snapshot', '--vault-path', self.vault,
                                           '--game', 'wo1', '--save-path', self.source, '--snapshot-label', 'Before')
        self.assertEqual((code, errors), (0, ''))
        first = json.loads(output)['id']
        code, output, errors = self.invoke('--vault-operation', 'branch', '--vault-path', self.vault,
                                           '--snapshot-id', first, '--vault-branch', 'alternate')
        self.assertEqual((code, errors), (0, ''))
        code, output, errors = self.invoke('--vault-operation', 'snapshot', '--vault-path', self.vault,
                                           '--game', 'wo1', '--save-path', self.source, '--vault-branch', 'alternate')
        self.assertEqual((code, errors), (0, ''))
        second = json.loads(output)['id']
        code, output, errors = self.invoke('--vault-operation', 'compare', '--vault-path', self.vault,
                                           '--snapshot-id', first, '--other-snapshot', second)
        self.assertEqual((code, errors), (0, ''))
        self.assertTrue(json.loads(output)['identical_gameplay_bytes'])
        restored = self.folder / 'restored'
        code, output, errors = self.invoke('--vault-operation', 'restore', '--vault-path', self.vault,
                                           '--snapshot-id', first, '--restore-dir', restored)
        self.assertEqual((code, errors), (0, ''))
        self.assertEqual((restored / self.source.name).read_bytes(), self.raw)
        code, output, errors = self.invoke('--vault-operation', 'verify', '--vault-path', self.vault)
        self.assertEqual((code, errors), (0, ''))
        self.assertTrue(all(item['valid'] for item in json.loads(output)))
        code, output, errors = self.invoke('--vault-operation', 'label', '--vault-path', self.vault,
                                           '--snapshot-id', second, '--snapshot-label', 'After')
        self.assertEqual((code, errors), (0, ''))
        code, output, errors = self.invoke('--vault-operation', 'list', '--vault-path', self.vault, '--vault-branch', 'alternate')
        self.assertEqual((code, errors), (0, ''))
        self.assertEqual(next(item for item in json.loads(output) if item['id'] == second)['label'], 'After')
        code, output, errors = self.invoke('--vault-operation', 'delete', '--vault-path', self.vault, '--snapshot-id', second)
        self.assertEqual((code, errors), (0, ''))
        self.assertEqual(len(SaveVault(self.vault).list_snapshots()), 1)
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_restore_refuses_existing_and_live_destinations_without_overwriting(self):
        vault = SaveVault.create(self.vault)
        snapshot = vault.snapshot('wo1', self.source)
        existing = self.folder / 'exists'
        existing.mkdir()
        sentinel = existing / self.source.name
        sentinel.write_bytes(b'keep')
        for destination in (existing, self.folder / 'Steam/userdata/123/456/remote'):
            code, output, errors = self.invoke('--vault-operation', 'restore', '--vault-path', self.vault,
                                               '--snapshot-id', snapshot.id, '--restore-dir', destination)
            self.assertEqual((code, output), (1, ''))
            self.assertNotIn(str(destination), errors)
        self.assertEqual(sentinel.read_bytes(), b'keep')

    def test_argument_validation_precedes_io_and_no_modifiers_leak_into_legacy_workflows(self):
        invalid = (
            ('--save-doctor', self.source), ('--save-doctor', '', '--game', 'wo1'),
            ('--save-doctor', self.source, '--game', 'wo1', '--discover-saves'),
            ('--save-doctor', self.source, '--game', 'wo1', '--recursive'),
            ('--save-doctor', self.source, '--game', 'wo1', '--comparison-report', ''),
            ('--discover-saves', '--game', 'wo1'), ('--discover-saves', '--list-games'),
            ('--discover-saves', '--dry-run'), ('--discover-saves', '--vault-path', self.vault),
            ('--vault-operation', 'create'), ('--vault-operation', 'create', '--vault-path', self.vault, '--game', 'wo1'),
            ('--vault-operation', 'snapshot', '--vault-path', self.vault, '--game', 'wo1'),
            ('--vault-operation', 'restore', '--vault-path', self.vault, '--snapshot-id', 'a'),
            ('--vault-operation', 'label', '--vault-path', self.vault, '--snapshot-id', 'a'),
            ('--list-games', '--vault-path', self.vault), ('--expected-sha256', '0' * 64),
            ('--scan-saves', self.folder, '--game', 'wo1', '--steam-root', self.folder),
        )
        with patch.object(SaveVault, 'create', side_effect=AssertionError('Invalid command wrote storage')):
            for arguments in invalid:
                with self.subTest(arguments=arguments):
                    code, output, errors = self.invoke(*arguments)
                    self.assertEqual((code, output), (2, ''))
                    self.assertIn('error:', errors)
        self.assertFalse(self.vault.exists())

    def test_operational_errors_are_private(self):
        with patch('koei_editor.shared.save_doctor.inspect_save', side_effect=OSError('PRIVATE OWNER PATH')):
            code, output, errors = self.invoke('--save-doctor', self.source, '--game', 'wo1')
        self.assertEqual((code, output), (1, ''))
        self.assertNotIn('PRIVATE', errors)
        code, output, errors = self.invoke('--vault-operation', 'list', '--vault-path', self.folder / 'missing-private')
        self.assertEqual((code, output), (1, ''))
        self.assertNotIn('missing-private', errors)

    def test_installed_entrypoint_runs_from_another_directory_without_display(self):
        result = subprocess.run([sys.executable, '-m', 'koei_editor', '--game', 'wo1', '--save-doctor', str(self.source)],
                                cwd=self.folder, env=dict(os.environ, DISPLAY=''), capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['success'])
        self.assertEqual(self.source.read_bytes(), self.raw)


if __name__ == '__main__':
    unittest.main()
