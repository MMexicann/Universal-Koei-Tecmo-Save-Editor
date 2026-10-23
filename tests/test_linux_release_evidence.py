"""Linux evidence binds complete tested source and exact extracted asset bytes."""
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from tools import package_linux, run_tests, smoke_linux


class LinuxEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for name in ('src', 'tools', 'tests', 'test-results'):
            (self.root / name).mkdir()
        (self.root / 'src/public.py').write_text('value = 7\n', encoding='utf-8')
        (self.root / 'pyproject.toml').write_text('[project]\nname="test"\n', encoding='utf-8')
        (self.root / 'tests/test_public.py').write_text('# Inventoried procedural test module.\n', encoding='utf-8')
        self.addCleanup(patch.stopall)
        patch.object(run_tests, 'ROOT', self.root).start()

    def suite(self):
        record = {'module': 'test_public.py', 'success': True, 'tests': 1, 'discovered_tests': 1,
                  'failures': 0, 'errors': 0, 'skipped': 0, 'expected_failures': 0,
                  'unexpected_successes': 0, 'duration_seconds': 0.1, 'discovery_errors': []}
        return {'schema_version': run_tests.SCHEMA_VERSION, 'source_fingerprint': run_tests.source_fingerprint(self.root / 'tests'),
                'inventory': ['test_public.py'], 'assignments': [['test_public.py']], 'shards': 1,
                'shard_index': 0, 'modules': [record], 'success': True, 'source_changed': False,
                'counts': run_tests.total_counts([record]), 'platform': 'linux', 'python': '3.13.13'}

    def write_suite(self, report):
        (self.root / 'test-results/linux.json').write_text(json.dumps(report), encoding='utf-8')

    def test_complete_successful_native_report_is_bound_to_exact_bytes_and_source(self):
        report = self.suite()
        self.write_suite(report)
        evidence = smoke_linux._suite_evidence(self.root)
        self.assertEqual(evidence['source_fingerprint'], report['source_fingerprint'])
        self.assertEqual(evidence['module_count'], 1)
        self.assertEqual(evidence['sha256'], hashlib.sha256((self.root / 'test-results/linux.json').read_bytes()).hexdigest())
        (self.root / 'src/public.py').write_text('value = 8\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            smoke_linux._suite_evidence(self.root)

    def test_failed_stale_missing_inventory_and_non_native_reports_are_rejected(self):
        for mutate in (lambda value: value.update(success=False),
                       lambda value: value.update(source_changed=True),
                       lambda value: value.update(inventory=[]),
                       lambda value: value.update(platform='win32'),
                       lambda value: value.update(python='3.12.12')):
            report = self.suite()
            mutate(report)
            self.write_suite(report)
            with self.assertRaises(ValueError):
                smoke_linux._suite_evidence(self.root)
        self.write_suite(self.suite())
        (self.root / 'tests/test_extra.py').write_text('# Missing from prior successful report.\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            smoke_linux._suite_evidence(self.root)

    def test_archive_hash_size_permissions_equal_actual_extracted_files(self):
        if os.name == 'nt':
            self.skipTest('Executable Linux mode comparison requires POSIX permissions.')
        top = 'Toolkit'
        entries = {'Toolkit': b'procedural launcher', 'cli/Toolkit-CLI': b'procedural CLI',
                   '_internal/public.json': b'{"public":true}'}
        destination = self.root / 'toolkit.tar.gz'
        package_linux.write_tar(destination, entries, top, {top, 'cli/' + top + '-CLI'})
        extracted = self.root / 'extracted'
        extracted.mkdir()
        for name, data in entries.items():
            path = extracted / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(0o755 if name in {top, 'cli/' + top + '-CLI'} else 0o644)
        archived = smoke_linux._archive_snapshot(destination, top)
        self.assertEqual(archived, smoke_linux._snapshot(extracted))
        (extracted / '_internal/public.json').write_bytes(b'changed')
        self.assertNotEqual(archived, smoke_linux._snapshot(extracted))

    def test_archive_links_unsafe_members_and_duplicate_entries_are_rejected(self):
        cases = []
        link = tarfile.TarInfo('Toolkit/link'); link.type = tarfile.SYMTYPE; link.linkname = '/outside'
        cases.append([(link, b'')])
        unsafe = tarfile.TarInfo('Toolkit/../escape'); unsafe.size = 1
        cases.append([(unsafe, b'x')])
        duplicate = tarfile.TarInfo('Toolkit/duplicate'); duplicate.size = 1
        cases.append([(duplicate, b'x'), (duplicate, b'x')])
        for number, members in enumerate(cases):
            destination = self.root / f'bad-{number}.tar.gz'
            with tarfile.open(destination, 'w:gz') as archive:
                for member, data in members:
                    archive.addfile(member, io.BytesIO(data))
            with self.subTest(number=number), self.assertRaises(ValueError):
                smoke_linux._archive_snapshot(destination, 'Toolkit')

    def test_cbc_doctor_probe_uses_selected_profile_and_refuses_mutation_or_extra_outputs(self):
        raw = b'Procedural probe bytes; actual native CBC is exercised by frozen smoke.'
        expected = {'success': True, 'read_only': True, 'sha256': hashlib.sha256(raw).hexdigest()}
        folder = self.root / 'cbc-probe'
        folder.mkdir()
        with patch.object(smoke_linux, '_bounded', return_value=json.dumps(expected)) as command:
            smoke_linux._doctor_probe(Path('tool'), folder, {}, 'wo4_pc', raw, 'cbc.bin')
        self.assertEqual(command.call_args.args[0], ['tool', 'doctor', '--game', 'wo4_pc', str(folder / 'cbc.bin')])
        for number, action in enumerate(('mutate', 'extra', 'foreign_digest')):
            private = self.root / f'negative-{number}'
            private.mkdir()
            def result(_command, cwd, _env):
                value = dict(expected)
                if action == 'mutate':
                    (cwd / 'cbc.bin').write_bytes(b'changed')
                elif action == 'extra':
                    (cwd / 'unexpected-output').write_bytes(b'new')
                else:
                    value['sha256'] = '0' * 64
                return json.dumps(value)
            with self.subTest(action=action), patch.object(smoke_linux, '_bounded', side_effect=result):
                with self.assertRaises(ValueError):
                    smoke_linux._doctor_probe(Path('tool'), private, {}, 'wo4_pc', raw, 'cbc.bin')


if __name__ == '__main__':
    unittest.main()
