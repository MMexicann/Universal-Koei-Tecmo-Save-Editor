"""Hash-bound runtime metadata and pre-bundle exclusion of build provenance."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import build_windows as build
from tools import package_release as release

PROJECT = Path(__file__).resolve().parents[1]


class RuntimeMetadataTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'tools/requirements').mkdir(parents=True)
        self.lock = self.root / 'tools/requirements/build.txt'
        self.original_lock = (PROJECT / 'tools/requirements/build.txt').read_text(encoding='utf-8')
        self.lock.write_text(self.original_lock, encoding='utf-8')
        self.metadata = {name: ('Metadata-Version: 2.4\nName: synthetic-' + name + '\n').encode()
                         for name in release.RUNTIME_DEPENDENCY_METADATA}
        hashes = patch.dict(release.RUNTIME_DEPENDENCY_METADATA,
                            {name: hashlib.sha256(data).hexdigest() for name, data in self.metadata.items()},
                            clear=True)
        hashes.start()
        self.addCleanup(hashes.stop)
        self.datas = []
        for index, (name, data) in enumerate(self.metadata.items()):
            source = self.root / f'metadata-{index}'
            source.write_bytes(data)
            self.datas.append((name, str(source), 'DATA'))

    def test_current_complete_wheel_lock_is_required(self):
        release.verify_dependency_metadata_lock(self.root)
        self.assertEqual(len(release.REVIEWED_WHEEL_HASHES), 12)
        self.assertEqual(len(self.metadata), 5)
        for name in self.metadata:
            self.assertIn(name.split('/')[0], release.REVIEWED_WHEEL_HASHES)

    def test_changed_hash_version_extra_requirement_or_lock_syntax_is_rejected(self):
        digest = next(iter(release.REVIEWED_WHEEL_HASHES.values()))
        candidates = [self.original_lock.replace(digest, '0' * 64),
                      self.original_lock.replace('numpy==2.5.4', 'numpy==2.5.5'),
                      self.original_lock + '\nunknown==1.0 --hash=sha256:' + '0' * 64 + '\n',
                      self.original_lock + '\nunknown[extra]==1.0 \\\n+ --hash=sha256:' + '0' * 64 + '\n',
                      self.original_lock.replace('--require-hashes\n', ''),
                      self.original_lock + '\n--extra-index-url https://example.invalid\n',
                      self.original_lock + '\n--require-hashes\n']
        for index, text in enumerate(candidates):
            self.lock.write_text(text, encoding='utf-8')
            with self.subTest(case=index), self.assertRaisesRegex(ValueError, 'lock'):
                release.verify_dependency_metadata_lock(self.root)

    def test_only_verified_metadata_is_retained_and_other_data_is_untouched(self):
        ordinary = ('licenses/NumPy-LICENSE.txt', 'already-collected-license', 'DATA')
        data = self.datas + [ordinary]
        for directory in release.REVIEWED_WHEEL_HASHES:
            for leaf in ('DELVEWHEEL', 'WHEEL', 'RECORD', 'INSTALLER', 'REQUESTED',
                         'direct_url.json', 'entry_points.txt', 'licenses/LICENSE.txt'):
                # Excluded build metadata is never opened or copied.
                data.append((directory + '/' + leaf, 'nonexistent-build-metadata', 'DATA'))
        filtered = release.filter_runtime_metadata(data, self.root)
        self.assertEqual(filtered, self.datas + [ordinary])
        self.assertIs(filtered[-1], ordinary)

    def test_missing_unknown_nested_duplicate_or_invalid_collection_fails(self):
        candidates = [self.datas[:-1],
                      self.datas + [('foreign-1.0.dist-info/METADATA', '', 'DATA')],
                      self.datas + [('_tcl_data/foreign.dist-info/METADATA', '', 'DATA')],
                      self.datas + [('numpy-2.5.4.dist-info/nested.dist-info/METADATA', '', 'DATA')],
                      self.datas + [self.datas[0]],
                      self.datas + [('numpy-2.5.4.dist-info/WHEEL', '', 'BINARY')],
                      self.datas + [('numpy-2.5.4.dist-info/../METADATA', '', 'DATA')],
                      self.datas + [('broken',)]]
        for index, data in enumerate(candidates):
            with self.subTest(case=index), self.assertRaises(ValueError):
                release.filter_runtime_metadata(data, self.root)

    def test_retained_metadata_hash_substitution_is_rejected_before_bundling(self):
        source = Path(self.datas[0][1])
        source.write_bytes(source.read_bytes() + b'tampered')
        with self.assertRaisesRegex(ValueError, 'differs from the pinned wheel'):
            release.filter_runtime_metadata(self.datas, self.root)

    def test_runtime_metadata_still_passes_privacy_and_exact_path_checks(self):
        for name, data in self.metadata.items():
            self.assertEqual(release._validate_runtime_file(name, data, {}), name)
            with self.assertRaisesRegex(ValueError, 'differs from the pinned wheel'):
                release._validate_runtime_file(name, data + b'tampered', {})
        for name in ('numpy-2.5.4.dist-info/DELVEWHEEL', 'numpy-2.5.4.dist-info/INSTALLER',
                     'numpy-2.5.4.dist-info/private.json', 'numpy-2.5.5.dist-info/METADATA',
                     '_tcl_data/foreign.dist-info/METADATA'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Unreviewed dependency metadata'):
                release._validate_runtime_file(name, b'unreviewed', {})
        name = next(iter(self.metadata))
        private = ('C:' + '/Users/' + 'PrivateOwner/' + 'build.py').encode()
        with patch.dict(release.RUNTIME_DEPENDENCY_METADATA, {name: hashlib.sha256(private).hexdigest()}):
            with self.assertRaisesRegex(ValueError, 'Personal home path'):
                release._validate_runtime_file(name, private, {})

    def test_metadata_source_reads_are_bounded(self):
        name, source, _ = self.datas[0]
        oversized = b'x' * 70000
        Path(source).write_bytes(oversized)
        with patch.dict(release.RUNTIME_DEPENDENCY_METADATA, {name: hashlib.sha256(oversized).hexdigest()}):
            with self.assertRaisesRegex(ValueError, 'differs from the pinned wheel'):
                release.filter_runtime_metadata(self.datas, self.root)

    def test_both_modes_explicitly_collect_required_runtime_metadata(self):
        expected = {name.split('-')[0] for name in self.metadata}
        for standalone in (False, True):
            args = build.build_args(standalone=standalone)
            collected = {args[index + 1] for index, item in enumerate(args) if item == '--copy-metadata'}
            self.assertEqual(collected, expected)
            excluded = {args[index + 1] for index, item in enumerate(args) if item == '--exclude-module'}
            self.assertEqual(excluded, {'setuptools', 'distutils', 'pkg_resources'})
            for module in ('cffi', '_cffi_backend', 'numpy', 'trimesh', 'miniaudio', '_miniaudio'):
                self.assertIn(module, args)
            self.assertIn('--noupx', args)
            self.assertIn('--onefile' if standalone else '--onedir', args)

    def test_filter_runs_after_analysis_before_either_bundle_assembly(self):
        for standalone in (False, True):
            spec = self.root / ('onefile.spec' if standalone else 'onedir.spec')
            spec.write_text('a = Analysis()\npyz = PYZ(a.pure)\nexe = EXE(a.datas)\n'
                            + ('' if standalone else 'bundle = COLLECT(a.datas)\n'), encoding='utf-8')
            build.filter_build_spec(spec, self.root)
            events = []

            class Analysis:
                def __init__(instance):
                    events.append('analysis')
                    instance.datas = self.datas + [('numpy-2.5.4.dist-info/DELVEWHEEL', '', 'DATA')]
                    instance.pure = []

            def bundle(data):
                events.append('bundle')
                self.assertEqual(data, self.datas)

            namespace = {'Analysis': Analysis, 'PYZ': lambda data: events.append('pyz'),
                         'EXE': bundle, 'COLLECT': bundle}
            exec(compile(spec.read_text(encoding='utf-8'), str(spec), 'exec'), namespace)
            self.assertEqual(events, ['analysis', 'pyz', 'bundle'] + ([] if standalone else ['bundle']))

    def test_unexpected_or_already_filtered_spec_is_rejected_without_overwriting(self):
        for source in ('a = None\n', 'a = Analysis()\na = Analysis()\n',
                       'a = Analysis()\n# filter_runtime_metadata\n'):
            spec = self.root / 'unexpected.spec'
            spec.write_text(source, encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Unexpected generated'):
                build.filter_build_spec(spec, self.root)
            self.assertEqual(spec.read_text(encoding='utf-8'), source)


if __name__ == '__main__':
    unittest.main()
