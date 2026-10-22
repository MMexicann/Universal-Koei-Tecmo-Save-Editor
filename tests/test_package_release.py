"""Release archive integrity and publication boundaries; synthetic files only."""
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch
import zipfile

from tools import package_release as release

PROJECT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.area = (PROJECT / 'work/package-tests').resolve()
        self.area.mkdir(parents=True, exist_ok=True)
        self.root = self.area / uuid.uuid4().hex
        self.root.mkdir()
        self.sources = {name: b'Public document\n' for name in release.WINDOWS_DOCS}
        self.sources.update({name: b'# Public build helper\n' for name in release.TOOL_FILES})
        self.sources.update({name: b'# Public community schema or guide\n'
                             for name in release.COMMUNITY_SCHEMA_FILES | release.SOURCE_ONLY_GUIDES})
        self.sources.update({f'src/koei_editor/data/{name}': b'{}' for name in release.RUNTIME_DATA})
        self.sources.update({name: b'Reviewed runtime license text\n' for name in release.RUNTIME_LICENSES})
        self.sources.update({
            'src/koei_editor/__init__.py': b'# Runtime package\n',
            'src/koei_editor/application.py': b"VERSION = '1.0'\n",
            'src/koei_editor/game_registry.py': b'# Registered game modules\n',
            'src/koei_editor/__main__.py': b'from .application import main\n',
            'tools/build_windows.py': b"VERSION = '1.0'\n",
            'pyproject.toml': b'[project]\nname = "synthetic-public-editor"\nversion = "1.0"\n',
            'launch.pyw': b'from koei_editor.application import main\nmain()\n',
            'docs/RELEASE_NOTES.md': b'# v1.0\n',
            '.github/workflows/windows-release.yml': b'name: Windows release\n',
            'licenses/Python-LICENSE.txt': b'License text\n',
            'tests/test_public.py': b'# Synthetic public test\n',
        })
        self.add_sources(self.sources)
        self.write_manifest()
        self.runtime = release.runtime_directory(self.root)
        self.runtime.mkdir(parents=True)
        release.executable_path(self.root).write_bytes(b'MZ synthetic editor executable')
        self.write_runtime_resources()
        for name in ('python314.dll', '_tkinter.pyd', 'tcl86t.dll', 'tk86t.dll'):
            (self.runtime / '_internal' / name).write_bytes(b'MZ synthetic native runtime dependency')
        for name in ('_tcl_data/init.tcl', '_tk_data/tk.tcl'):
            target = self.runtime / '_internal' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'# Tcl/Tk runtime resource\n')
        with zipfile.ZipFile(self.runtime / '_internal/base_library.zip', 'w') as library:
            library.writestr('encodings/__init__.pyc', b'public compiled standard library')
            library.writestr('encodings/utf_8.pyc', b'public compiled standard library')
        standalone = release.standalone_executable_path(self.root)
        standalone.parent.mkdir(parents=True)
        standalone.write_bytes(b'MZ synthetic self-contained executable, distinct from portable launcher')

    def tearDown(self):
        assert self.root.resolve().is_relative_to(self.area)
        shutil.rmtree(self.root)

    def add_sources(self, additions):
        self.sources.update(additions)
        for name, data in additions.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        if hasattr(self, 'runtime'):
            self.write_runtime_resources()

    def write_runtime_resources(self):
        for name, data in release.embedded_metadata(self.sources).items():
            path = self.runtime / '_internal' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    def write_manifest(self, extra=()):
        entries = [{'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                   for name, data in self.sources.items()]
        entries.extend(extra)
        (self.root / release.MANIFEST).write_text(json.dumps({'version': '1.0', 'files': entries}), encoding='utf-8')

    def archive_fixture(self):
        blobs = dict(release.embedded_metadata(self.sources))
        blobs['PYZ.pyz'] = b'compressed archive'
        module = [b'public Python module']
        pyz = SimpleNamespace(toc={'koei_editor.application': (0, 0, 0)}, extract=lambda name, raw=False: module[0])
        archive = SimpleNamespace(toc={name: (0, 0, 0, 0, 'z' if name == 'PYZ.pyz' else 'x') for name in blobs},
                                  extract=lambda name: blobs[name], open_embedded_archive=lambda name: pyz)
        return archive, blobs, module

    def standalone_archive_fixture(self):
        archive, _blobs, module = self.archive_fixture()
        blobs = {name.removeprefix('_internal/'): data
                 for name, data in release._runtime_snapshot(self.root, self.sources).items()
                 if name.startswith('_internal/')}
        blobs['PYZ.pyz'] = b'compressed archive'
        pyz = archive.open_embedded_archive('PYZ.pyz')
        standalone = SimpleNamespace(toc={name: (0, 0, 0, 0, 'z' if name == 'PYZ.pyz' else 'b') for name in blobs},
                                     extract=lambda name: blobs[name], open_embedded_archive=lambda name: pyz)
        return standalone, blobs, module

    def test_standalone_requires_embedded_runtime_and_never_uses_portable_dependencies(self):
        archive, blobs, _ = self.standalone_archive_fixture()
        shutil.rmtree(self.runtime)
        expected_path = release.standalone_executable_path(self.root)
        def reader(path):
            self.assertEqual(Path(path), expected_path)
            return archive
        self.assertEqual(release.verify_standalone(self.root, reader), len(blobs))
        for name in ('python314.dll', '_tkinter.pyd', 'base_library.zip', 'tcl86t.dll',
                     'tk86t.dll', '_tcl_data/init.tcl', '_tk_data/tk.tcl',
                     'koei_editor/data/game_metadata.json', 'licenses/LICENSE',
                     'licenses/THIRD_PARTY_NOTICES.md', *release.RUNTIME_LICENSES):
            entry = archive.toc.pop(name)
            with self.subTest(missing=name), self.assertRaisesRegex(ValueError, 'missing'):
                release.verify_standalone(self.root, reader)
            archive.toc[name] = entry

    def test_dependency_license_sources_are_required_before_packaging_either_format(self):
        for name in release.RUNTIME_LICENSES:
            original = self.sources.pop(name)
            self.write_manifest()
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Required public sources'):
                release.verified_sources(self.root)
            self.sources[name] = original
        self.write_manifest()

    def test_standalone_checks_embedded_metadata_native_files_modules_and_privacy(self):
        archive, blobs, module = self.standalone_archive_fixture()
        for name, data in (('koei_editor/data/game_metadata.json', b'{"tampered": true}'),
                           ('licenses/LICENSE', b'wrong license'),
                           ('python314.dll', b'non-PE native dependency'),
                           ('_tkinter.pyd', b'broken extension')):
            original = blobs[name]
            blobs[name] = data
            with self.subTest(changed=name), self.assertRaisesRegex(ValueError, 'differs from manifest|invalid native'):
                release.verify_standalone(self.root, lambda _: archive)
            blobs[name] = original
        for name in ('private.sav', 'fixtures/native.pyc', '../escape.dll',
                     'owner.json', 'AttachedGame.dll', 'private_extension.pyd'):
            archive.toc[name] = (0, 0, 0, 0, 'b')
            blobs[name] = b'MZ unreviewed content'
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Private or unsafe|Unreviewed'):
                release.verify_standalone(self.root, lambda _: archive)
            del archive.toc[name]
        module[0] = ('C:' + '/Users/' + 'PrivateOwner/' + 'hidden.py').encode()
        with self.assertRaisesRegex(ValueError, 'Personal home path'):
            release.verify_standalone(self.root, lambda _: archive)
        module[0] = b'public module'
        pyz = archive.open_embedded_archive('PYZ.pyz')
        pyz.toc['koei_editor.tests.private_fixture'] = (0, 0, 0)
        with self.assertRaisesRegex(ValueError, 'Private or unsafe module'):
            release.verify_standalone(self.root, lambda _: archive)

    def test_standalone_cannot_be_a_portable_launcher_or_external_alias(self):
        portable_archive, _, _ = self.archive_fixture()
        with self.assertRaisesRegex(ValueError, 'runtime dependencies missing'):
            release.verify_standalone(self.root, lambda _: portable_archive)
        path = release.standalone_executable_path(self.root)
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'standalone executable is missing'):
            release.verify_standalone(self.root)
        try:
            path.symlink_to(release.executable_path(self.root))
        except OSError as error:
            self.skipTest('Symlinks are unavailable: ' + str(error))
        with self.assertRaisesRegex(ValueError, 'escapes'):
            release.verify_standalone(self.root)

    def test_standalone_races_and_failed_validation_prevent_release_downloads(self):
        archive, _, _ = self.standalone_archive_fixture()
        path = release.standalone_executable_path(self.root)
        def reader(_):
            path.write_bytes(b'MZ changed standalone executable')
            return archive
        with self.assertRaisesRegex(ValueError, 'changed during validation'):
            release.verify_standalone(self.root, reader)
        with patch.object(release, 'verify_executable', return_value=1), \
             patch.object(release, 'verify_standalone', side_effect=ValueError('Standalone runtime is incomplete')):
            with self.assertRaisesRegex(ValueError, 'Standalone runtime is incomplete'):
                release.package(self.root)
        self.assertFalse((self.root / 'release').exists())
        with patch.object(release, 'verify_executable', return_value=1), \
             patch.object(release, 'verify_standalone', side_effect=lambda _: path.write_bytes(b'MZ another change')):
            with self.assertRaisesRegex(ValueError, 'changed during validation'):
                release.package(self.root)
        self.assertFalse((self.root / 'release').exists())

    def test_standalone_copy_keeps_verified_bytes_and_detects_source_change(self):
        standalone = release.standalone_executable_path(self.root)
        original = standalone.read_bytes()
        writer = release.write_zip
        def changed_after_validation(path, entries):
            writer(path, entries)
            standalone.write_bytes(b'MZ changed while ZIPs were written')
        with patch.object(release, 'verify_executable', return_value=1), \
             patch.object(release, 'verify_standalone', return_value=1), \
             patch.object(release, 'write_zip', side_effect=changed_after_validation):
            with self.assertRaisesRegex(ValueError, 'changed during release copying'):
                release.package(self.root)
        copied = self.root / 'release' / (release.artifact_name(self.root) + '.exe')
        self.assertEqual(copied.read_bytes(), original)
        self.assertFalse((self.root / 'release/SHA256SUMS.txt').exists())

    def test_archives_contain_only_verified_sources_and_user_downloads(self):
        (self.root / 'work').mkdir()
        (self.root / 'work/private.sav').write_bytes(b'private fixture')
        with patch.object(release, 'verify_executable', return_value=1) as verified, \
             patch.object(release, 'verify_standalone', return_value=1) as standalone_verified:
            assets = release.package(self.root)
        verified.assert_called_once_with(self.root)
        standalone_verified.assert_called_once_with(self.root)
        with zipfile.ZipFile(assets[0]) as archive:
            prefix = 'UniversalKoeiTecmoSaveEditor-v1.0/'
            runtime = release._runtime_snapshot(self.root, self.sources)
            self.assertEqual(set(archive.namelist()), {prefix + name for name in runtime})
            self.assertEqual({name.split('/')[0] for name in archive.namelist()}, {prefix.rstrip('/')})
            for name, data in runtime.items():
                self.assertEqual(archive.read(prefix + name), data)
        with zipfile.ZipFile(assets[1]) as archive:
            prefix = 'UniversalKoeiTecmoSaveEditor-v1.0-Source/'
            self.assertEqual(set(archive.namelist()), {prefix + name for name in self.sources} | {prefix + release.MANIFEST})
            for name, data in self.sources.items():
                self.assertEqual(archive.read(prefix + name), data)
        self.assertEqual(len(assets), 4)
        self.assertEqual(assets[2].read_bytes(), release.standalone_executable_path(self.root).read_bytes())
        self.assertNotEqual(assets[2].read_bytes(), release.executable_path(self.root).read_bytes())
        self.assertEqual(assets[3].read_text().splitlines(),
                         [f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}' for path in assets[:3]])
        with patch.object(release, 'verify_executable', return_value=1), patch.object(release, 'verify_standalone', return_value=1):
            second = release.package(self.root, self.root / 'second-output')
        self.assertEqual(assets[1].read_bytes(), second[1].read_bytes())
        with patch.object(release, 'verify_executable', return_value=1), patch.object(release, 'verify_standalone', return_value=1), self.assertRaises(ValueError):
            release.package(self.root)

    def test_actual_windows_zip_contains_exact_reviewed_guides_collected_by_builder(self):
        from tools import build_windows
        for source in release.RUNTIME_GUIDES:
            self.assertIn((source, 'guides'), build_windows.DATA)
        with patch.object(release, 'verify_executable', return_value=1), patch.object(release, 'verify_standalone', return_value=1):
            assets = release.package(self.root)
        with zipfile.ZipFile(assets[0]) as archive:
            for source in release.RUNTIME_GUIDES:
                target = 'UniversalKoeiTecmoSaveEditor-v1.0/_internal/guides/' + source.removeprefix('docs/')
                self.assertEqual(archive.read(target), self.sources[source])
            # Follow the shipped guide's local links so a new workflow guide
            # cannot be documented yet omitted from the actual archive.
            text = (PROJECT / 'docs/EDIT_PRESETS.md').read_text(encoding='utf-8')
            for linked in re.findall(r'\]\(([^():]+\.md)\)', text):
                target = 'UniversalKoeiTecmoSaveEditor-v1.0/_internal/guides/' + linked
                self.assertIn(target, archive.namelist(), f'Missing linked user guide: {linked}')
            self.assertFalse(any('/src/' in name or '/AGENTS.md' in name for name in archive.namelist()))

    def test_missing_changed_and_unreviewed_guides_fail_runtime_validation(self):
        source = release.RUNTIME_GUIDES[0]
        name = 'guides/' + source.removeprefix('docs/')
        path = self.runtime / '_internal' / name
        opened = path.read_bytes()
        archive, _blobs, _module = self.archive_fixture()
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            release.verify_executable(self.root, lambda _: archive)
        path.write_bytes(b'changed guide')
        with self.assertRaisesRegex(ValueError, 'differs from manifest'):
            release.verify_executable(self.root, lambda _: archive)
        path.write_bytes(opened)
        unreviewed = path.with_name('private-notes.md')
        unreviewed.write_bytes(b'unreviewed text')
        with self.assertRaises(ValueError):
            release.verify_executable(self.root, lambda _: archive)
        unreviewed.unlink()
        standalone, blobs, _module = self.standalone_archive_fixture()
        self.assertIn(name, standalone.toc)
        blobs[name] = b'changed embedded guide'
        with self.assertRaisesRegex(ValueError, 'differs from manifest'):
            release.verify_standalone(self.root, lambda _: standalone)

    def test_hash_mismatch_prevents_any_release_output(self):
        (self.root / 'README.md').write_text('Changed after manifest', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'hash or length mismatch'):
            release.package(self.root)
        self.assertFalse((self.root / 'release').exists())

    def test_windows_zip_is_clean_while_source_zip_retains_developer_documents(self):
        additions = {'docs/README.md': b'[Remaining inputs](REMAINING_INPUTS.md)\n',
                     'docs/REMAINING_INPUTS.md': b'# Exact further input requirements\n',
                     'docs/releases/v0.9.md': b'# Reviewed historical release\n'}
        self.add_sources(additions)
        self.write_manifest()
        (self.root / 'docs/private-investigation.md').write_bytes(b'Unreviewed research')
        with patch.object(release, 'verify_executable', return_value=1), patch.object(release, 'verify_standalone', return_value=1):
            assets = release.package(self.root)
        with zipfile.ZipFile(assets[0]) as archive:
            for name in additions:
                self.assertNotIn(name, archive.namelist())
            self.assertNotIn('AGENTS.md', archive.namelist())
            self.assertNotIn('CONTRIBUTING.md', archive.namelist())
            self.assertNotIn('docs/private-investigation.md', archive.namelist())
            self.assertNotIn('src/koei_editor/application.py', archive.namelist())
            for name in release.RUNTIME_LICENSES:
                self.assertEqual(archive.read('UniversalKoeiTecmoSaveEditor-v1.0/_internal/' + name), self.sources[name])
        with zipfile.ZipFile(assets[1]) as archive:
            prefix = 'UniversalKoeiTecmoSaveEditor-v1.0-Source/'
            for name, data in additions.items():
                self.assertEqual(archive.read(prefix + name), data)

    def test_traversal_and_private_file_entries_are_rejected_before_reading(self):
        for name in ('../private.sav', 'work/private.sav', 'tests/fixture.sav', 'C:/private.sav',
                     'src/koei_editor/games/../private.sav', 'licenses/private.exe', '.git/config',
                     'tests/.runs/test_example.py', 'src/koei_editor/data/account.json',
                     'src/koei_editor/data/sample.dat', 'tools/private_dump.py', 'src/foreign/codec.py',
                     'application.py', 'SOURCE_MANIFEST.json', release.MANIFEST):
            with self.subTest(name=name), self.assertRaises(ValueError):
                release.public_path(name)

    def test_contributor_scaffold_and_test_helper_paths_are_narrowly_allowed(self):
        self.assertEqual(release.public_path('.gitattributes').as_posix(), '.gitattributes')
        for name in release.ADAPTER_TEMPLATE_FILES | release.PUBLIC_TEST_HELPERS | release.PUBLIC_GUIDES:
            with self.subTest(name=name):
                self.assertEqual(release.public_path(name).as_posix(), name)
        for name in ('tools/adapter_template/private.dat', 'tools/adapter_template/fixture.json',
                     'tools/adapter_template/another_parser.py', 'tools/adapter_template/nested/new_game_parser.py',
                     'tools/adapter_template/INSTRUCTIONS.md/../private.dat', 'tools/adapter_template/.private.txt',
                     'tools/adapter_template/new_game_parser.py.bak', 'tests/another_helper.py',
                     'tests/scalar_contract.py/../private.dat', 'tests/helpers/scalar_contract.py'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                release.public_path(name)

    def test_community_schema_paths_are_explicitly_whitelisted(self):
        for name in release.COMMUNITY_SCHEMA_FILES | release.COMMUNITY_TEMPLATE_FILES:
            with self.subTest(name=name):
                self.assertEqual(release.public_path(name).as_posix(), name)
        for name in ('docs/schemas/private.schema.json', 'docs/schemas/../private.schema.json',
                     'tools/community_package_templates/private.json'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                release.public_path(name)

    def test_present_git_text_policy_is_required_and_packaged_byte_exactly(self):
        policy = b'*.py text eol=lf\n*.json text eol=lf\n'
        (self.root / '.gitattributes').write_bytes(policy)
        with self.assertRaisesRegex(ValueError, 'Required public sources.*gitattributes'):
            release.verified_sources(self.root)
        self.add_sources({'.gitattributes': policy})
        self.write_manifest()
        with patch.object(release, 'verify_executable', return_value=1), patch.object(release, 'verify_standalone', return_value=1):
            assets = release.package(self.root)
        with zipfile.ZipFile(assets[1]) as archive:
            self.assertEqual(archive.read('UniversalKoeiTecmoSaveEditor-v1.0-Source/.gitattributes'), policy)

    def test_personal_path_duplicate_and_mismatched_versions_are_rejected(self):
        self.add_sources({'README.md': ('Local path ' + 'C:' + '/Users/' + 'PrivateOwner/' + 'Documents').encode()})
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'personal home path'):
            release.verified_sources(self.root)
        self.add_sources({'README.md': b'Public document\n'})
        self.write_manifest([{'path': 'src/koei_editor/application.py', 'bytes': 0, 'sha256': '0' * 64}])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            release.verified_sources(self.root)
        self.write_manifest()
        (self.root / 'tools/build_windows.py').write_text("VERSION='2.0'\n", encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'versions do not match'):
            release.verified_sources(self.root)

    def test_embedded_metadata_and_compressed_modules_are_verified(self):
        archive, blobs, module = self.archive_fixture()
        reader = lambda executable: archive
        self.assertEqual(release.verify_executable(self.root, reader), len(blobs))
        module[0] = ('C:' + '/Users/' + 'PrivateOwner/' + 'file.py').encode()
        with self.assertRaisesRegex(ValueError, 'Personal home path'):
            release.verify_executable(self.root, reader)
        module[0] = b'public Python module'
        data_name = 'koei_editor/data/game_metadata.json'
        blobs[data_name] = b'wrong metadata'
        with self.assertRaisesRegex(ValueError, 'differs from manifest'):
            release.verify_executable(self.root, reader)
        blobs[data_name] = self.sources['src/' + data_name]
        archive.toc['private.sav'] = (0, 0, 0, 0, 'x')
        with self.assertRaisesRegex(ValueError, 'Private or unsafe'):
            release.verify_executable(self.root, reader)

    def test_missing_external_runtime_or_metadata_prevents_publication(self):
        archive, _, _ = self.archive_fixture()
        for name in ('python314.dll', '_tkinter.pyd', 'tcl86t.dll', 'tk86t.dll',
                     'base_library.zip', '_tcl_data/init.tcl', '_tk_data/tk.tcl',
                     'koei_editor/data/game_metadata.json'):
            target = self.runtime / '_internal' / name
            original = target.read_bytes()
            target.unlink()
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'missing'):
                release.verify_executable(self.root, lambda _: archive)
            self.assertFalse((self.root / 'release').exists())
            target.write_bytes(original)
        library = self.runtime / '_internal/base_library.zip'
        with zipfile.ZipFile(library, 'w') as output:
            output.writestr('empty.pyc', b'not the complete standard library')
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            release.verify_executable(self.root, lambda _: archive)

    def test_external_metadata_and_native_dependencies_are_strictly_reviewed(self):
        archive, _, _ = self.archive_fixture()
        target = self.runtime / '_internal/koei_editor/data/game_metadata.json'
        target.write_bytes(b'{"tampered": true}')
        with self.assertRaisesRegex(ValueError, 'differs from manifest'):
            release.verify_executable(self.root, lambda _: archive)
        self.write_runtime_resources()
        for name in ('koei_editor/data/owner.json', 'AttachedGame.dll', 'private_extension.pyd',
                     '_tcl_data/injected.py', '_tk_data/hidden.zip', 'helper.exe'):
            target = self.runtime / '_internal' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'MZ unreviewed content')
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Unreviewed|Private or unsafe'):
                release.verify_executable(self.root, lambda _: archive)
            target.unlink()
        for name in ('python314.dll', '_tkinter.pyd'):
            target = self.runtime / '_internal' / name
            original = target.read_bytes()
            target.write_bytes(b'invalid dependency')
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'invalid native'):
                release.verify_executable(self.root, lambda _: archive)
            target.write_bytes(original)

    def test_external_private_files_personal_paths_and_nested_archives_are_scanned(self):
        archive, _, _ = self.archive_fixture()
        for name in ('private.sav', 'source-fixtures/native.pyc', 'tests/private.txt',
                     '_tcl_data/.private.txt', '_tcl_data/save.dat'):
            target = self.runtime / '_internal' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'private fixture')
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Private or unsafe'):
                release.verify_executable(self.root, lambda _: archive)
            target.unlink()
            while target.parent != self.runtime / '_internal' and not any(target.parent.iterdir()):
                parent = target.parent
                parent.rmdir()
                target = parent
        target = self.runtime / '_internal/_tcl_data/init.tcl'
        original = target.read_bytes()
        target.write_bytes(('C:' + '/Users/' + 'PrivateOwner/' + 'file').encode())
        with self.assertRaisesRegex(ValueError, 'Personal home path'):
            release.verify_executable(self.root, lambda _: archive)
        target.write_bytes(original)
        target = self.runtime / '_internal/base_library.zip'
        original = target.read_bytes()
        for name in ('../owner.pyc', 'tests/fixture.pyc', 'owner.json', 'player.sav'):
            with zipfile.ZipFile(target, 'w') as library:
                library.writestr(name, b'private fixture')
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Private or unsafe|Unreviewed JSON'):
                release.verify_executable(self.root, lambda _: archive)
        target.write_bytes(original)

    def test_runtime_file_and_parent_symlinks_cannot_escape_the_distribution(self):
        archive, _, _ = self.archive_fixture()
        target = self.runtime / '_internal/koei_editor/data/game_metadata.json'
        original = target.read_bytes()
        target.unlink()
        try:
            target.symlink_to(self.root / 'README.md')
        except OSError as error:
            self.skipTest('Symlinks are unavailable: ' + str(error))
        with self.assertRaisesRegex(ValueError, 'symlink'):
            release.verify_executable(self.root, lambda _: archive)
        target.unlink()
        target.write_bytes(original)
        directory = self.runtime / '_internal/_tcl_data'
        moved = self.root / 'moved_tcl_data'
        directory.rename(moved)
        directory.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            release.verify_executable(self.root, lambda _: archive)

    def test_runtime_changes_during_verification_cannot_be_packaged(self):
        archive, _, _ = self.archive_fixture()
        target = self.runtime / '_internal/_tcl_data/init.tcl'
        def reader(_):
            target.write_bytes(b'# changed after runtime snapshot\n')
            return archive
        with self.assertRaisesRegex(ValueError, 'changed during validation'):
            release.verify_executable(self.root, reader)
        with patch.object(release, 'verify_executable', side_effect=lambda _: target.write_bytes(b'# changed again\n')):
            with self.assertRaisesRegex(ValueError, 'changed during validation'):
                release.package(self.root)
        self.assertFalse((self.root / 'release').exists())

    def test_tcl9_dll_embedded_resources_are_required_and_privacy_scanned(self):
        archive, _, _ = self.archive_fixture()
        def dll(prefix, entry, extra=None):
            buffer = io.BytesIO(b'MZ synthetic Tcl/Tk DLL prefix')
            with zipfile.ZipFile(buffer, 'a') as resources:
                resources.writestr(prefix + '/' + entry, b'# Native Tcl/Tk script\n')
                if extra:
                    resources.writestr(*extra)
            return buffer.getvalue()
        internal = self.runtime / '_internal'
        for name in ('tcl86t.dll', 'tk86t.dll'):
            (internal / name).unlink()
        shutil.rmtree(internal / '_tcl_data')
        shutil.rmtree(internal / '_tk_data')
        (internal / 'tcl90.dll').write_bytes(dll('tcl_library', 'init.tcl'))
        (internal / 'tcl9tk90.dll').write_bytes(dll('tk_library', 'tk.tcl'))
        for name in ('libtommath.dll', 'zlib1.dll', '_zstd.pyd'):
            (internal / name).write_bytes(b'MZ synthetic standard runtime dependency')
        release.verify_executable(self.root, lambda _: archive)
        target = internal / 'tcl90.dll'
        good = target.read_bytes()
        for extra in (('tcl_library/player.sav', b'private fixture'),
                      ('tcl_library/owner.json', b'{}'),
                      ('tcl_library/inject.py', b'unreviewed code'),
                      ('../escape.tcl', b'# escape'),
                      ('tcl_library/private.tcl', ('C:' + '/Users/' + 'PrivateOwner/').encode())):
            target.write_bytes(dll('tcl_library', 'init.tcl', extra))
            with self.subTest(entry=extra[0]), self.assertRaises(ValueError):
                release.verify_executable(self.root, lambda _: archive)
        target.write_bytes(dll('tcl_library', 'incomplete.tcl'))
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            release.verify_executable(self.root, lambda _: archive)
        target.write_bytes(good)
        dependency = internal / 'zlib1.dll'
        dependency.unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            release.verify_executable(self.root, lambda _: archive)
        dependency.write_bytes(b'MZ synthetic standard runtime dependency')
        standalone, blobs, _ = self.standalone_archive_fixture()
        release.verify_standalone(self.root, lambda _: standalone)
        blobs['tcl90.dll'] = dll('tcl_library', 'incomplete.tcl')
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            release.verify_standalone(self.root, lambda _: standalone)
        blobs['tcl90.dll'] = dll('tcl_library', 'init.tcl', ('tcl_library/player.sav', b'private'))
        with self.assertRaisesRegex(ValueError, 'Private or unsafe'):
            release.verify_standalone(self.root, lambda _: standalone)


if __name__ == '__main__':
    unittest.main()
