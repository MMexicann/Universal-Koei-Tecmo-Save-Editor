"""Publication verifies captured Linux evidence; no downloaded program is run."""
import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import package_linux, package_release, run_tests, smoke_linux
from tools import verify_linux_publication as publication


class LinuxPublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / 'source'
        for name in ('src/koei_editor', 'tools', 'tests'):
            (self.root / name).mkdir(parents=True)
        (self.root / 'src/koei_editor/application.py').write_text("VERSION='1.0.1'\n", encoding='utf-8')
        (self.root / 'tools/build_windows.py').write_text("VERSION='1.0.1'\n", encoding='utf-8')
        (self.root / 'pyproject.toml').write_text('[project]\nversion="1.0.1"\n', encoding='utf-8')
        (self.root / 'tests/test_public.py').write_text('# Procedural source inventory.\n', encoding='utf-8')
        self.sources = {package_release.MANIFEST: b'{"public":"procedural manifest"}\n'}
        for target, value in ((run_tests, self.root),):
            patched = patch.object(target, 'ROOT', value)
            patched.start(); self.addCleanup(patched.stop)
        source_review = patch.object(package_release, 'verified_sources', return_value=('1.0.1', self.sources))
        source_review.start(); self.addCleanup(source_review.stop)
        self.artifact, self.output = self.base / 'downloaded', self.base / 'release'
        (self.artifact / 'release').mkdir(parents=True)
        (self.artifact / 'test-results').mkdir()
        self.output.mkdir()
        self.stem = package_release.artifact_name(self.root) + '-Linux-x86_64'
        self.archive = self.artifact / 'release' / (self.stem + '.tar.gz')
        self.checksum = self.artifact / 'release' / (self.stem + '.SHA256SUMS')
        self.report_name = 'LinuxVerification-v1.0.1.json'
        self.files = {self.stem: b'procedural GUI, never execute',
                      'cli/' + self.stem + '-CLI': b'procedural CLI, never execute'}
        self.files.update({prefix + name: b'procedural AES native bytes'
                           for prefix in ('_internal/', 'cli/_internal/')
                           for name in publication.AES_NATIVE_FILES})
        self.rebuild_archive()
        record = dict(module='test_public.py', success=True, tests=1, discovered_tests=1,
                      failures=0, errors=0, skipped=0, expected_failures=0, unexpected_successes=0,
                      duration_seconds=0.1, discovery_errors=[])
        self.suite = dict(schema_version=run_tests.SCHEMA_VERSION,
                          source_fingerprint=run_tests.source_fingerprint(self.root / 'tests'),
                          inventory=['test_public.py'], assignments=[['test_public.py']], shards=1,
                          shard_index=0, modules=[record], success=True, source_changed=False,
                          counts=run_tests.total_counts([record]), platform='linux', python='3.13.13')
        self.smoke = dict(schema_version=1, platform='linux-x86_64', clean=True, version='1.0.1',
                          fixture_scope='procedural_only', commands=sorted(publication.REQUIRED_COMMANDS),
                          source_manifest_sha256=hashlib.sha256(self.sources[package_release.MANIFEST]).hexdigest(),
                          archive=self.archive_record(), runtime=smoke_linux._archive_snapshot(self.archive, self.stem),
                          runtime_files=len(self.files))
        self.write_evidence()

    def rebuild_archive(self):
        self.archive.unlink(missing_ok=True)
        package_linux.write_tar(self.archive, self.files, self.stem, {self.stem, 'cli/' + self.stem + '-CLI'})
        raw = self.archive.read_bytes()
        self.checksum.write_text(hashlib.sha256(raw).hexdigest() + '  ' + self.archive.name + '\n', encoding='ascii')

    def archive_record(self):
        raw = self.archive.read_bytes()
        return dict(file_name=self.archive.name, sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw))

    def write_evidence(self):
        raw = (json.dumps(self.suite) + '\n').encode()
        (self.artifact / 'test-results/linux.json').write_bytes(raw)
        self.smoke['suite'] = dict(sha256=hashlib.sha256(raw).hexdigest(),
                                   source_fingerprint=self.suite['source_fingerprint'], module_count=1,
                                   counts=self.suite['counts'], platform=self.suite['platform'], python=self.suite['python'])
        (self.artifact / 'test-results/linux-smoke.json').write_text(json.dumps(self.smoke), encoding='utf-8')

    def verify(self):
        return publication.verify_publication(self.artifact, self.output, root=self.root)

    def assert_rejected(self):
        with self.assertRaises((ValueError, OSError, KeyError, TypeError)):
            self.verify()
        self.assertEqual(list(self.output.iterdir()), [])

    def test_verified_exact_bytes_and_evidence_are_staged_without_executing_anything(self):
        with patch.object(subprocess, 'Popen', side_effect=AssertionError('Downloaded binaries must never execute')):
            report = self.verify()
        self.assertTrue(report['success'])
        self.assertFalse(report['in_game_verified'])
        self.assertEqual((self.output / self.archive.name).read_bytes(), self.archive.read_bytes())
        report_raw = (self.output / self.report_name).read_bytes()
        self.assertEqual(json.loads(report_raw), report)
        self.assertNotIn(str(self.base).encode(), report_raw)
        expected = self.archive_record()['sha256'] + '  ' + self.archive.name + '\n'
        expected += hashlib.sha256(report_raw).hexdigest() + '  ' + self.report_name + '\n'
        self.assertEqual((self.output / self.checksum.name).read_text(encoding='ascii'), expected)
        self.assertEqual({path.name for path in self.output.iterdir()}, {self.archive.name, self.checksum.name, self.report_name})

    def test_foreign_source_missing_inventory_and_failed_suite_are_rejected(self):
        original = copy.deepcopy(self.suite)
        for change in (dict(source_fingerprint='0' * 64), dict(inventory=[]), dict(success=False),
                       dict(source_changed=True), dict(platform='win32'), dict(python='3.12.12')):
            self.suite = {**copy.deepcopy(original), **change}
            self.write_evidence()
            with self.subTest(change=change):
                self.assert_rejected()

    def test_changed_source_since_suite_is_not_published(self):
        (self.root / 'src/koei_editor/application.py').write_text("VERSION='1.0.1'\nchanged=True\n", encoding='utf-8')
        self.assert_rejected()

    def test_smoke_version_manifest_suite_and_required_commands_cannot_be_forged(self):
        original = copy.deepcopy(self.smoke)
        changes = [dict(version='1.0'), dict(clean=False), dict(source_manifest_sha256='0' * 64),
                   dict(platform='windows-x86_64'), dict(fixture_scope='real_player_files'),
                   dict(commands=['version']), dict(runtime_files=1),
                   dict(commands=sorted(publication.REQUIRED_COMMANDS - {'doctor-procedural-aes-cbc'}))]
        for change in changes:
            self.smoke = {**copy.deepcopy(original), **change}
            self.write_evidence()
            with self.subTest(change=change):
                self.assert_rejected()
        self.smoke = copy.deepcopy(original)
        self.write_evidence()
        path = self.artifact / 'test-results/linux-smoke.json'
        forged = json.loads(path.read_bytes()); forged['suite']['sha256'] = '0' * 64
        path.write_text(json.dumps(forged), encoding='utf-8')
        self.assert_rejected()

    def test_archive_byte_and_runtime_map_tampering_are_rejected(self):
        original = self.archive.read_bytes()
        self.archive.write_bytes(original + b'tampered')
        self.assert_rejected()
        self.archive.write_bytes(original)
        checksum = self.checksum.read_bytes()
        self.archive.write_bytes(b'not a gzip archive')
        self.checksum.write_text(self.archive_record()['sha256'] + '  ' + self.archive.name + '\n', encoding='ascii')
        self.smoke['archive'] = self.archive_record()
        self.write_evidence()
        self.assert_rejected()
        self.archive.write_bytes(original)
        self.checksum.write_bytes(checksum)
        self.smoke['archive'] = self.archive_record()
        runtime = self.smoke['runtime'][self.stem]
        runtime['sha256'] = '0' * 64
        self.write_evidence()
        self.assert_rejected()

    def test_coherent_archive_and_smoke_still_require_both_native_cbc_copies(self):
        del self.files['cli/_internal/Crypto/Cipher/_raw_cbc.abi3.so']
        self.rebuild_archive()
        self.smoke.update(archive=self.archive_record(), runtime=smoke_linux._archive_snapshot(self.archive, self.stem),
                          runtime_files=len(self.files))
        self.write_evidence()
        self.assert_rejected()

    def test_existing_any_output_is_rejected_before_staging(self):
        existing = self.output / self.report_name
        existing.write_bytes(b'foreign report')
        with self.assertRaises(FileExistsError):
            self.verify()
        self.assertEqual({path.name for path in self.output.iterdir()}, {self.report_name})
        self.assertEqual(existing.read_bytes(), b'foreign report')

    def test_input_leaf_and_parent_aliases_are_never_followed(self):
        private = self.base / 'private.json'; private.write_bytes(b'not evidence')
        selected = self.artifact / 'test-results/linux.json'
        selected.unlink()
        try:
            selected.symlink_to(private)
        except OSError as error:
            self.skipTest('Native symlink creation unavailable: ' + type(error).__name__)
        self.assert_rejected()
        selected.unlink(); self.write_evidence()
        moved = self.base / 'held-results'
        (self.artifact / 'test-results').rename(moved)
        (self.artifact / 'test-results').symlink_to(moved, target_is_directory=True)
        self.assert_rejected()
        self.assertEqual(private.read_bytes(), b'not evidence')

    def test_output_dangling_alias_and_late_collision_preserve_foreign_entries(self):
        target = self.base / 'must-not-exist.tar.gz'
        alias = self.output / self.archive.name
        try:
            alias.symlink_to(target)
        except OSError as error:
            self.skipTest('Native symlink creation unavailable: ' + type(error).__name__)
        with self.assertRaises(FileExistsError):
            self.verify()
        self.assertFalse(target.exists())
        alias.unlink()
        publish = publication.publish_new_child_bound
        def collide(raw, parent, name, identity, **kwargs):
            (self.output / name).write_bytes(b'foreign race winner')
            return publish(raw, parent, name, identity, **kwargs)
        with patch.object(publication, 'publish_new_child_bound', side_effect=collide):
            with self.assertRaises((ValueError, OSError)):
                self.verify()
        self.assertEqual(alias.read_bytes(), b'foreign race winner')
        self.assertEqual({path.name for path in self.output.iterdir()}, {self.archive.name})

    def test_duplicate_json_keys_and_oversized_inputs_are_rejected(self):
        path = self.artifact / 'test-results/linux-smoke.json'
        path.write_bytes(b'{"clean":true,"clean":false}')
        self.assert_rejected()
        self.write_evidence()
        with patch.object(publication, 'MAX_ARCHIVE_BYTES', 1):
            self.assert_rejected()

    def test_input_directory_identity_swap_is_rejected_before_foreign_content_read(self):
        selected = self.artifact / 'test-results'
        foreign = self.base / 'foreign-results'
        foreign.mkdir()
        private = foreign / 'linux.json'
        private.write_bytes(b'SYNTHETIC_PRIVATE_NEVER_READ')
        original = publication._directory
        swapped = []
        @contextmanager
        def replace(bindings):
            if bindings[-1][0] == selected and not swapped:
                selected.rename(self.base / 'held-results')
                foreign.rename(selected)
                swapped.append(True)
            with original(bindings) as directory:
                yield directory
        with patch.object(publication, '_directory', replace):
            self.assert_rejected()
        self.assertTrue(swapped)
        self.assertEqual((selected / 'linux.json').read_bytes(), b'SYNTHETIC_PRIVATE_NEVER_READ')

    def test_hardlinked_inputs_are_rejected_without_staging(self):
        path = self.artifact / 'test-results/linux.json'
        try:
            os.link(path, self.base / 'linked-input.json')
        except OSError as error:
            self.skipTest('Native hardlink creation unavailable: ' + type(error).__name__)
        self.assert_rejected()

    def test_verifier_import_and_help_need_only_standard_library(self):
        root = Path(__file__).resolve().parents[1]
        environment = dict(os.environ, PYTHONPATH=os.pathsep.join((str(root), str(root / 'src'))))
        result = subprocess.run([sys.executable, '-S', '-m', 'tools.verify_linux_publication', '--help'],
                                env=environment, text=True, encoding='utf-8', capture_output=True, timeout=30)
        self.assertEqual((result.returncode, result.stderr), (0, ''))
        self.assertIn('--artifact-dir', result.stdout)
        result = subprocess.run([sys.executable, '-S', '-m', 'tools.verify_linux_publication',
                                 '--artifact-dir', '', '--output-dir', str(self.output)],
                                env=environment, text=True, encoding='utf-8', capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertEqual(list(self.output.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
