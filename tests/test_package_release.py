"""Release archive integrity and publication boundaries; synthetic files only."""
import hashlib
import io
import json
from pathlib import Path
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
        self.sources.update({f'src/koei_editor/data/{name}': b'{}' for name in release.RUNTIME_DATA})
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

    def test_archives_contain_only_verified_sources_and_user_downloads(self):
        (self.root / 'work').mkdir()
        (self.root / 'work/private.sav').write_bytes(b'private fixture')
        with patch.object(release, 'verify_executable', return_value=1) as verified:
            assets = release.package(self.root)
        verified.assert_called_once_with(self.root)
        with zipfile.ZipFile(assets[0]) as archive:
            reviewed_docs = {name for name in self.sources if name.startswith('docs/') and name.endswith('.md')}
            prefix = 'UniversalKoeiTecmoSaveEditor-v1.0/'
            runtime = release._runtime_snapshot(self.root, self.sources)
            self.assertEqual(set(archive.namelist()), set(release.WINDOWS_DOCS) | reviewed_docs |
                             {'licenses/Python-LICENSE.txt'} | {prefix + name for name in runtime})
            for name, data in runtime.items():
                self.assertEqual(archive.read(prefix + name), data)
        with zipfile.ZipFile(assets[1]) as archive:
            prefix = 'UniversalKoeiTecmoSaveEditor-v1.0-Source/'
            self.assertEqual(set(archive.namelist()), {prefix + name for name in self.sources} | {prefix + release.MANIFEST})
            for name, data in self.sources.items():
                self.assertEqual(archive.read(prefix + name), data)
        self.assertEqual(len(assets), 3)
        self.assertFalse(any(path.suffix == '.exe' for path in assets))
        self.assertEqual(assets[2].read_text().splitlines(),
                         [f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}' for path in assets[:2]])
        with patch.object(release, 'verify_executable', return_value=1):
            second = release.package(self.root, self.root / 'second-output')
        self.assertEqual(assets[1].read_bytes(), second[1].read_bytes())
        with patch.object(release, 'verify_executable', return_value=1), self.assertRaises(ValueError):
            release.package(self.root)

    def test_hash_mismatch_prevents_any_release_output(self):
        (self.root / 'README.md').write_text('Changed after manifest', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'hash or length mismatch'):
            release.package(self.root)
        self.assertFalse((self.root / 'release').exists())

    def test_windows_zip_ships_reviewed_documentation_index_and_supplier_checklist_only(self):
        additions = {'docs/README.md': b'[Remaining inputs](REMAINING_INPUTS.md)\n',
                     'docs/REMAINING_INPUTS.md': b'# Exact further input requirements\n',
                     'docs/releases/v0.9.md': b'# Reviewed historical release\n'}
        self.add_sources(additions)
        self.write_manifest()
        (self.root / 'docs/private-investigation.md').write_bytes(b'Unreviewed research')
        with patch.object(release, 'verify_executable', return_value=1):
            windows_zip = release.package(self.root)[0]
        with zipfile.ZipFile(windows_zip) as archive:
            for name, data in additions.items():
                self.assertEqual(archive.read(name), data)
            self.assertNotIn('docs/private-investigation.md', archive.namelist())
            self.assertNotIn('src/koei_editor/application.py', archive.namelist())

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

    def test_present_git_text_policy_is_required_and_packaged_byte_exactly(self):
        policy = b'*.py text eol=lf\n*.json text eol=lf\n'
        (self.root / '.gitattributes').write_bytes(policy)
        with self.assertRaisesRegex(ValueError, 'Required public sources.*gitattributes'):
            release.verified_sources(self.root)
        self.add_sources({'.gitattributes': policy})
        self.write_manifest()
        with patch.object(release, 'verify_executable', return_value=1):
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


if __name__ == '__main__':
    unittest.main()
