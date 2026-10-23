"""Independent omission and privacy checks for the nested source package."""
import io
import unittest
import zipfile
from unittest.mock import patch

from tools import package_release as release
from tools import refresh_manifest
from tools import run_tests
from tests import test_universal_packaging as packaging_fixture

BASE = packaging_fixture.BASE


class RegisteredDependencyReviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = packaging_fixture.UniversalPackagingTests('test_universal_sources_cannot_omit_game_module_from_manifest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def sources(self, additions):
        self.fixture.add_sources(additions)
        self.fixture.write_manifest()

    def test_keyword_editor_parser_and_relative_package_imports_require_complete_tree(self):
        prefix = BASE + 'games/new/'
        self.sources({
            BASE + 'game_registry.py': b"Game(id='new', editor_module='koei_editor.games.new.editor', parser_module='koei_editor.games.new.parser')\n",
            prefix + '__init__.py': b'from . import codec\n',
            prefix + 'editor.py': b'from . import parser\n',
            prefix + 'parser.py': b'from .codec import decode\n',
            prefix + 'codec.py': b'from ...shared import preferences\n',
        })
        release.verified_sources(self.fixture.root)
        for name in (prefix + '__init__.py', prefix + 'editor.py', prefix + 'parser.py', prefix + 'codec.py', BASE + 'games/__init__.py', BASE + '__init__.py'):
            original = self.fixture.sources.pop(name)
            self.fixture.write_manifest()
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Required public sources'):
                release.verified_sources(self.fixture.root)
            self.fixture.sources[name] = original

    def test_local_dependency_outside_runtime_namespace_cannot_disappear(self):
        package = self.fixture.root / 'foreign'
        package.mkdir()
        (package / '__init__.py').write_bytes(b'# Unreviewed package\n')
        (package / 'codec.py').write_bytes(b'# Required codec\n')
        for statement in (b'import foreign.codec\n', b'from foreign import codec\n', b'import foreign\n', b'from ... import escape\n'):
            self.sources({BASE + 'application.py': b"VERSION='1.0'\n" + statement})
            with self.subTest(statement=statement), self.assertRaises(ValueError):
                release.verified_sources(self.fixture.root)

    def test_every_embedded_data_file_requires_a_reviewed_source_entry(self):
        for leaf in release.RUNTIME_DATA:
            name = BASE + 'data/' + leaf
            original = self.fixture.sources.pop(name)
            self.fixture.write_manifest()
            with self.subTest(leaf=leaf), self.assertRaisesRegex(ValueError, 'Required public sources'):
                release.verified_sources(self.fixture.root)
            self.fixture.sources[name] = original

    def test_project_version_is_checked_without_importing_runtime(self):
        (self.fixture.root / 'pyproject.toml').write_bytes(b'[project]\nversion="1.1"\n')
        with self.assertRaisesRegex(ValueError, 'versions do not match'):
            release.version(self.fixture.root)

    def test_omitted_public_test_modules_prevent_release_until_explicitly_reviewed(self):
        omitted = {
            'tests/test_mod_workshop_assets.py': b'# Procedural assets tests\n',
            'tests/test_mod_workshop_gui.py': b'# Procedural GUI tests\n',
            'tests/test_mod_workshop_packaging.py': b'# Procedural packaging tests\n',
            'tests/test_mod_workshop_projects.py': b'# Procedural projects tests\n',
            'tests/test_mod_workshop_validation.py': b'# Procedural validation tests\n',
            'tests/test_playthrough_profiles.py': b'# Procedural profile tests\n',
        }
        root = self.fixture.root
        manifest_before = (root / release.MANIFEST).read_bytes()
        for name, data in omitted.items():
            (root / name).write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'Required public sources') as rejected:
            release.package(root)
        for name in omitted:
            self.assertIn(name, str(rejected.exception))
        self.assertFalse((root / 'release').exists())
        self.assertEqual((root / release.MANIFEST).read_bytes(), manifest_before)

        # Only an explicit audited manifest update permits these source bytes.
        self.sources(omitted)
        _, sources = release.verified_sources(root)
        self.assertTrue(set(omitted) <= sources.keys())
        with patch.object(run_tests, 'ROOT', root):
            expected_fingerprint = run_tests.source_fingerprint(root / 'tests')
        published = root / 'work/reconstructed-source'
        for name, data in sources.items():
            target = published / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        with patch.object(run_tests, 'ROOT', published):
            self.assertEqual(run_tests.source_fingerprint(published / 'tests'), expected_fingerprint)
        self.assertEqual(run_tests.inventory(published / 'tests'), run_tests.inventory(root / 'tests'))

    def test_suite_helpers_and_json_inputs_cannot_be_silently_excluded_or_auto_approved(self):
        root = self.fixture.root
        for name in ('src/koei_editor/review_helper.py', 'tools/unreviewed_helper.py',
                     'tests/scalar_contract.py', 'tests/private_context.json'):
            with self.subTest(name=name):
                target = root / name
                original = target.read_bytes() if target.exists() else None
                target.write_bytes(b'{}\n' if name.endswith('.json') else b'# Procedural helper\n')
                # Existing fixture helpers may already have explicit approval.
                prior_entry = self.fixture.sources.pop(name, None)
                self.fixture.write_manifest()
                before = (root / release.MANIFEST).read_bytes()
                try:
                    with self.assertRaisesRegex(ValueError, 'Required public sources') as rejected:
                        release.verified_sources(root)
                    self.assertIn(name, str(rejected.exception))
                    self.assertEqual((root / release.MANIFEST).read_bytes(), before)
                    if name.startswith('tools/') or name.endswith('.json'):
                        with self.assertRaisesRegex(ValueError, 'Not a public source file'):
                            release.public_path(name)
                finally:
                    if original is None:
                        target.unlink()
                    else:
                        target.write_bytes(original)
                    if prior_entry is not None:
                        self.fixture.sources[name] = prior_entry
                    self.fixture.write_manifest()

    def test_non_fingerprinted_work_and_cache_files_do_not_expand_public_sources(self):
        root = self.fixture.root
        for name in ('work/private.json', 'tests/__pycache__/ignored.py', 'tests/notes.txt'):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'Private procedural placeholder\n')
        _, sources = release.verified_sources(root)
        self.assertFalse({'work/private.json', 'tests/__pycache__/ignored.py', 'tests/notes.txt'} & sources.keys())

    def test_unreviewed_json_and_private_python_modules_are_rejected_in_bundle(self):
        archive, blobs, module = self.fixture.archive_fixture()
        archive.toc['koei_editor/data/owner.json'] = (0, 0, 0, 0, 'x')
        with self.assertRaisesRegex(ValueError, 'Unreviewed JSON'):
            release.verify_executable(self.fixture.root, lambda _: archive)
        del archive.toc['koei_editor/data/owner.json']
        pyz = archive.open_embedded_archive('PYZ.pyz')
        pyz.toc['koei_editor.tests.private_fixture'] = (0, 0, 0)
        with self.assertRaisesRegex(ValueError, 'Private or unsafe module'):
            release.verify_executable(self.fixture.root, lambda _: archive)


    def test_library_zip_cannot_hide_player_data_or_traversal_paths(self):
        archive, blobs, module = self.fixture.archive_fixture()
        archive.toc['base_library.zip'] = (0, 0, 0, 0, 'x')
        for name in ('sample.sav', '../private.pyc', 'fixtures/native.pyc', 'AttachedGame.exe', 'owner.json'):
            compressed = io.BytesIO()
            with zipfile.ZipFile(compressed, 'w') as library:
                library.writestr(name, b'opaque private payload')
            blobs['base_library.zip'] = compressed.getvalue()
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Private or unsafe|Unreviewed JSON'):
                release.verify_executable(self.fixture.root, lambda _: archive)
        compressed = io.BytesIO()
        with zipfile.ZipFile(compressed, 'w') as library:
            library.writestr('encodings/utf_8.pyc', b'public compiled library')
        blobs['base_library.zip'] = compressed.getvalue()
        release.verify_executable(self.fixture.root, lambda _: archive)

    def test_refresh_never_discovers_private_files_and_rolls_back_failed_candidate(self):
        root = self.fixture.root
        (root / 'private.sav').write_bytes(b'private')
        refresh_manifest.refresh(root)
        self.assertNotIn('private.sav', (root / release.MANIFEST).read_text())
        refreshed = (root / release.MANIFEST).read_bytes()
        with patch.object(refresh_manifest, 'verified_sources', side_effect=ValueError('incomplete candidate')):
            with self.assertRaisesRegex(ValueError, 'incomplete candidate'):
                refresh_manifest.refresh(root)
        self.assertEqual((root / release.MANIFEST).read_bytes(), refreshed)
        self.assertFalse(list((root / 'tools').glob('.SOURCE_MANIFEST.*.tmp')))

    def test_source_symlinks_are_rejected(self):
        root = self.fixture.root
        source = root / 'README.md'
        source.unlink()
        try:
            source.symlink_to(root / 'LICENSE')
        except OSError as exc:
            self.skipTest('Symlink creation unavailable: ' + str(exc))
        with self.assertRaisesRegex(ValueError, 'escapes'):
            release.verified_sources(root)
        with self.assertRaisesRegex(ValueError, 'escapes'):
            refresh_manifest.refresh(root)


    def test_manifest_parent_symlink_is_rejected_before_refresh_or_read(self):
        root = self.fixture.root
        original = root / 'tools'
        relocated = root / 'moved_tools'
        original.rename(relocated)
        try:
            original.symlink_to(relocated, target_is_directory=True)
        except OSError as exc:
            self.skipTest('Symlink creation unavailable: ' + str(exc))
        for operation in (release.verified_sources, refresh_manifest.refresh):
            with self.subTest(operation=operation.__name__), self.assertRaisesRegex(ValueError, 'escapes'):
                operation(root)


if __name__ == '__main__':
    unittest.main()
