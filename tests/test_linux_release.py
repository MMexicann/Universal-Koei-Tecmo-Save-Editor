"""Native Linux packaging contracts; all inputs here are procedural."""
import ast
import hashlib
import gzip
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import build_linux as build
from tools import linux_build_review as review
from tools import package_linux as package
from tools import package_release as release

ROOT = Path(__file__).resolve().parents[1]


class LinuxBuildReviewTests(unittest.TestCase):
    def test_native_build_reuses_game_resources_and_has_distinct_gui_cli_outputs(self):
        gui, cli = build.build_args(ROOT), build.build_args(ROOT, cli=True)
        for args in (gui, cli):
            self.assertIn('--onedir', args)
            self.assertIn('--console', args)
            self.assertNotIn('--onefile', args)
            self.assertEqual(args[args.index('--distpath') + 1], str(ROOT / 'dist-linux'))
            self.assertIn('Crypto.Cipher.AES', args)
            self.assertIn(str(ROOT / 'docs/LINUX.md') + ':guides', args)
            from koei_editor.game_registry import ALL_ADAPTERS
            for game in ALL_ADAPTERS:
                self.assertIn(game.parser_module, args)
        self.assertNotEqual(gui[gui.index('--name') + 1], cli[cli.index('--name') + 1])
        self.assertEqual(gui[-1], str(ROOT / 'launch.pyw'))
        self.assertEqual(cli[-1], str(ROOT / 'src/koei_editor/cli.py'))

    def test_linux_wheel_lock_closes_crypto_and_asset_dependencies_without_changing_windows(self):
        checked = review.verify_linux_lock(ROOT)
        self.assertEqual(checked['python'], '3.13')
        self.assertIn('pycryptodome-3.23.0.dist-info', checked['wheels'])
        self.assertIn('numpy-2.5.4.dist-info/METADATA', checked['runtime_metadata'])
        release.verify_dependency_metadata_lock(ROOT)
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary).resolve()
            (folder / 'tools/requirements').mkdir(parents=True)
            (folder / 'tools/linux_dependency_review.json').write_bytes((ROOT / 'tools/linux_dependency_review.json').read_bytes())
            (folder / 'licenses').mkdir()
            (folder / 'licenses/python-standalone-3.13.txt').write_bytes((ROOT / 'licenses/python-standalone-3.13.txt').read_bytes())
            lock = (ROOT / 'tools/requirements/linux-build.txt').read_text(encoding='utf-8')
            (folder / 'tools/requirements/linux-build.txt').write_text(lock.replace('--only-binary=:all:', ''), encoding='utf-8')
            with self.assertRaises(ValueError):
                review.verify_linux_lock(folder)

    def test_analysis_filters_unneeded_wheel_markers_and_requires_exact_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary).resolve() / 'metadata'
            data = b'Metadata-Version: 2.4\nName: procedural\n'
            source.write_bytes(data)
            name = 'procedural-1.dist-info/METADATA'
            checked = {'wheels': {'procedural-1.dist-info': 'wheel'},
                       'runtime_metadata': {name: hashlib.sha256(data).hexdigest()}}
            entries = [(name, str(source), 'DATA'),
                       ('procedural-1.dist-info/RECORD', str(source), 'DATA'),
                       ('_tk_data/tk.tcl', str(source), 'DATA')]
            with patch.object(review, 'verify_linux_lock', return_value=checked):
                self.assertEqual(review.filter_linux_metadata(entries), [entries[0], entries[2]])
                for bad in (entries[1:], entries + [entries[0]],
                            [('foreign-1.dist-info/METADATA', str(source), 'DATA')]):
                    with self.subTest(entries=bad), self.assertRaises(ValueError):
                        review.filter_linux_metadata(bad)
                source.write_bytes(b'Changed metadata')
                with self.assertRaises(ValueError):
                    review.filter_linux_metadata(entries)

    def test_provenance_transform_changes_only_reviewed_documentation_not_behavior(self):
        prefix = '/'.join(('', 'home', 'guido'))
        other = '/'.join(('', 'home', 'user'))
        source = ('"""' + prefix + '"""\n'
                  'class DataSource:\n    """' + ' '.join([prefix] * 6) + '"""\n'
                  '    value = 17 * 3\n'
                  'class Repository:\n    """' + other + '"""\n').encode()
        checked = {'numpy_sources': {'numpy/lib/_datasource.py': hashlib.sha256(source).hexdigest()}}
        with patch.object(review, 'verify_linux_lock', return_value=checked):
            code = review.reviewed_numpy_code('numpy.lib._datasource', source, 'procedural.py')
            namespace = {}
            exec(code, namespace)
            self.assertEqual(namespace['DataSource'].value, 51)
            self.assertNotIn(prefix, namespace['DataSource'].__doc__)
            self.assertEqual(namespace['Repository'].__doc__, '/example/data')
            with self.assertRaises(ValueError):
                review.reviewed_numpy_code('numpy.lib._datasource', source + b'\n', 'procedural.py')

    def test_spec_filter_is_inserted_before_executable_and_is_not_repeatable(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / 'test.spec'
            path.write_text('a = Analysis([])\npyz = PYZ(a.pure)\nexe = EXE(pyz)\n', encoding='utf-8')
            build.filter_build_spec(path)
            text = path.read_text(encoding='utf-8')
            ast.parse(text)
            self.assertLess(text.index('a.datas = filter_linux_metadata'), text.index('exe = EXE'))
            self.assertIn('a.exclude_system_libraries', text)
            with self.assertRaises(ValueError):
                build.filter_build_spec(path)


class LinuxArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.destination = self.root / 'release.tar.gz'

    def test_reproducible_new_only_archive_has_safe_names_permissions_and_no_owners_or_links(self):
        entries = {'tool': b'procedural ELF', 'cli/tool-cli': b'procedural CLI', '_internal/public.json': b'{}'}
        launchers = {'tool', 'cli/tool-cli'}
        package.write_tar(self.destination, entries, 'toolkit', launchers)
        expected = self.destination.read_bytes()
        with tarfile.open(fileobj=io.BytesIO(expected), mode='r:gz') as archive:
            self.assertEqual(len(archive.getmembers()), len(entries))
            for member in archive.getmembers():
                self.assertTrue(member.isfile())
                self.assertEqual((member.uid, member.gid, member.uname, member.gname, member.mtime), (0, 0, '', '', 0))
                leaf = member.name.removeprefix('toolkit/')
                self.assertEqual(member.mode, 0o755 if leaf in launchers else 0o644)
                self.assertEqual(archive.extractfile(member).read(), entries[leaf])
        second = self.root / 'second.tar.gz'
        package.write_tar(second, entries, 'toolkit', launchers)
        self.assertEqual(second.read_bytes(), expected)
        with self.assertRaises(FileExistsError):
            package.write_tar(self.destination, {'foreign': b'foreign'}, 'toolkit', set())
        self.assertEqual(self.destination.read_bytes(), expected)
        if os.name != 'nt':
            self.assertEqual(self.destination.stat().st_mode & 0o777, 0o600)

    def test_archive_refuses_unsafe_names_before_creating_output(self):
        for name in ('../escape', '/escape', 'tests/native.pyc', '_internal/player.sav', '_internal/account.json/../x'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                package.write_tar(self.destination, {name: b'private'}, 'toolkit', set())
            self.assertFalse(self.destination.exists())

    def test_native_whitelist_checks_architecture_exact_wheel_hash_and_unknown_libraries(self):
        elf = bytearray(64)
        elf[:6] = b'\x7fELF\x02\x01'
        elf[18:20] = (62).to_bytes(2, 'little')
        raw = bytes(elf)
        checked = {'native_wheel_files': {'numpy.libs/libreviewed.so': hashlib.sha256(raw).hexdigest()}}
        self.assertTrue(package._native_allowed('numpy.libs/libreviewed.so', raw, checked))
        self.assertTrue(package._native_allowed('libreviewed.so', raw, checked))
        self.assertFalse(package._native_allowed('numpy.libs/libreviewed.so', raw + b'changed', checked))
        self.assertFalse(package._native_allowed('libunknown.so', raw, checked))
        for forbidden in ('python3.13/lib-dynload/_dbm.cpython-313-x86_64-linux-gnu.so',
                          'thread3.0.4/libtcl9thread3.0.4.so', 'itcl4.3.5/libtcl9itcl4.3.5.so'):
            supplied = {'native_wheel_files': {}, 'python_runtime': {
                'native_files': {forbidden: hashlib.sha256(raw).hexdigest()}}}
            self.assertFalse(package._native_allowed(forbidden, raw, supplied))
        elf[18:20] = (183).to_bytes(2, 'little')
        self.assertFalse(package._native_allowed('libpython3.13.so.1.0', bytes(elf), checked))

    def test_official_tcl_resources_remain_bounded_and_private_or_unknown_content_is_refused(self):
        name = '_tcl_data/cookiejar0.2/public_suffix_list.dat.gz'
        self.assertTrue(package._tcl_resource(name, gzip.compress(b'public.example\n')))
        self.assertTrue(package._tcl_resource('tcl9/9.0/platform-1.1.0.tm', b'# public Tcl module'))
        self.assertTrue(package._tcl_resource('_tk_data/images/logo100.gif', b'GIF89a'))
        self.assertFalse(package._tcl_resource('_tcl_data/tclAppInit.c', b'sample C source'))
        self.assertFalse(package._tcl_resource('_tk_data/images/private.gif', b'private'))
        for bad in (b'not gzip', gzip.compress(b'public') + gzip.compress(b'extra'),
                    gzip.compress('/'.join(('', 'home', 'private-sentinel', 'x')).encode())):
            with self.subTest(data=bad[:8]), self.assertRaises(ValueError):
                package._tcl_resource(name, bad)

    def test_archive_destination_alias_and_late_collision_preserve_foreign_bytes(self):
        target = self.root / 'foreign'
        target.write_bytes(b'FOREIGN')
        try:
            self.destination.symlink_to(target)
        except OSError:
            self.skipTest('File symlink creation unavailable.')
        with self.assertRaises((ValueError, FileExistsError)):
            package.write_tar(self.destination, {'tool': b'public'}, 'toolkit', {'tool'})
        self.assertTrue(self.destination.is_symlink())
        self.assertEqual(target.read_bytes(), b'FOREIGN')
        self.destination.unlink()
        original = package.publish_new_child_bound
        def collide(data, parent, name, identity, **kwargs):
            self.destination.write_bytes(b'LATE_FOREIGN')
            return original(data, parent, name, identity, **kwargs)
        with patch.object(package, 'publish_new_child_bound', side_effect=collide) as publisher:
            with self.assertRaises((OSError, ValueError)):
                package.write_tar(self.destination, {'tool': b'public'}, 'toolkit', {'tool'})
        self.assertEqual(publisher.call_count, 1)
        self.assertEqual(self.destination.read_bytes(), b'LATE_FOREIGN')


@unittest.skipIf(os.name == 'nt', 'Native Linux executable permissions require POSIX.')
class LinuxRuntimeReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for name in ('src/koei_editor/application.py', 'tools/build_windows.py', 'pyproject.toml'):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('[project]\nversion="1.1"\n' if name.endswith('.toml') else "VERSION='1.1'\n", encoding='utf-8')
        self.folder = package.runtime_directory(self.root)
        self.folder.mkdir(parents=True)
        self.sources = {name: b'Public license' for name in build.LINUX_LICENSES}
        self.sources['docs/LINUX.md'] = b'Public Linux guide'
        self.expected = {'koei_editor/data/public.json': b'{}'}
        self.expected.update({name: self.sources[name] for name in build.LINUX_LICENSES})
        self.expected['guides/LINUX.md'] = self.sources['docs/LINUX.md']
        metadata = 'pycryptodome-3.23.0.dist-info/METADATA'
        self.checked = {'runtime_metadata': {metadata: hashlib.sha256(b'Public metadata').hexdigest()},
                        'native_wheel_files': {}}
        patches = (patch.object(package, 'verify_linux_lock', return_value=self.checked),
                   patch.object(release, 'embedded_metadata', return_value={'koei_editor/data/public.json': b'{}'}),
                   patch.dict(release.TRIMESH_RESOURCES, {}, clear=True),
                   patch.object(package, '_verify_modules'))
        for patched in patches:
            patched.start()
            self.addCleanup(patched.stop)
        self.elf = bytearray(64)
        self.elf[:6] = b'\x7fELF\x02\x01'
        self.elf[18:20] = (62).to_bytes(2, 'little')
        self.checked['native_wheel_files'] = {
            name: hashlib.sha256(self.elf).hexdigest() for name in review.AES_NATIVE_FILES}
        self.checked['python_runtime'] = {'native_files': {
            name: hashlib.sha256(self.elf).hexdigest() for name in (
                *review.REQUIRED_PROVIDER_NATIVE, 'libpython3.13.so')}}
        self.launcher = self.folder / build.artifact_name(self.root)
        self.launcher.write_bytes(self.elf)
        self.launcher.chmod(0o755)
        files = dict(self.expected)
        files.update({metadata: b'Public metadata', 'libpython3.13.so.1.0': bytes(self.elf),
                      'python3.13/lib-dynload/_tkinter.cpython-313-x86_64-linux-gnu.so': bytes(self.elf)})
        files.update({name: bytes(self.elf) for name in review.AES_NATIVE_FILES})
        files.update({name: bytes(self.elf) for name in review.REQUIRED_PROVIDER_NATIVE})
        for name, data in files.items():
            path = self.folder / '_internal' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        with zipfile.ZipFile(self.folder / '_internal/base_library.zip', 'w') as library:
            library.writestr('encodings/__init__.pyc', b'procedural public bytecode')
            library.writestr('encodings/utf_8.pyc', b'procedural public bytecode')

    def test_complete_inventory_is_required_and_resource_bytes_are_pinned(self):
        result = package.runtime_snapshot(self.root, self.sources)
        self.assertIn(self.launcher.name, result)
        resource = self.folder / '_internal/koei_editor/data/public.json'
        resource.write_bytes(b'{"changed": true}')
        with self.assertRaisesRegex(ValueError, 'reviewed sources'):
            package.runtime_snapshot(self.root, self.sources)
        resource.write_bytes(b'{}')
        (self.folder / '_internal/python3.13/lib-dynload/_tkinter.cpython-313-x86_64-linux-gnu.so').unlink()
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            package.runtime_snapshot(self.root, self.sources)

    def test_extra_private_resources_and_wrong_architecture_are_refused(self):
        private = self.folder / '_internal/owner.json'
        private.write_bytes(b'{"private":true}')
        with self.assertRaisesRegex(ValueError, 'Unreviewed'):
            package.runtime_snapshot(self.root, self.sources)

        private.unlink()
        self.elf[18:20] = (183).to_bytes(2, 'little')
        self.launcher.write_bytes(self.elf)
        with self.assertRaisesRegex(ValueError, 'x86_64 ELF'):
            package.runtime_snapshot(self.root, self.sources)

    def test_missing_cbc_native_provider_is_refused_before_packaging(self):
        (self.folder / '_internal/Crypto/Cipher/_raw_cbc.abi3.so').unlink()
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            package.runtime_snapshot(self.root, self.sources)

    def test_each_missing_bundled_tk_library_is_refused_before_packaging(self):
        for name in ('libtcl9.0.so', 'libtcl9tk9.0.so'):
            library = self.folder / '_internal' / name
            library.unlink()
            with self.subTest(library=name), self.assertRaisesRegex(ValueError, 'incomplete'):
                package.runtime_snapshot(self.root, self.sources)
            library.write_bytes(self.elf)

    def test_only_internal_native_aliases_may_be_expanded(self):
        alias = self.folder / '_internal/libpython3.13.so'
        try:
            alias.symlink_to('libpython3.13.so.1.0')
        except OSError:
            self.skipTest('File symlink creation unavailable.')
        result = package.runtime_snapshot(self.root, self.sources)
        self.assertEqual(result['_internal/libpython3.13.so'], bytes(self.elf))
        alias.unlink()
        outside = self.root / 'outside.so'
        outside.write_bytes(self.elf)
        alias.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'escapes'):
            package.runtime_snapshot(self.root, self.sources)
        self.assertEqual(outside.read_bytes(), self.elf)


if __name__ == '__main__':
    unittest.main()
