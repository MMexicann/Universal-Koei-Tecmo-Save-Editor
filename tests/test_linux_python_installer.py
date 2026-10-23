"""Procedural archives qualify the Linux build interpreter bootstrap only."""
import hashlib
import io
import os
from pathlib import Path
import stat
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from tools import install_linux_python as installer


class LinuxPythonInstallerTests(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory()
        self.addCleanup(area.cleanup)
        self.root = Path(area.name).resolve()
        self.work = self.root / 'work'
        self.work.mkdir()
        self.destination = self.work / 'interpreter'
        self.cache = self.work / 'cache'
        root_patch = patch.object(installer, 'ROOT', self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        self.payload = b'Procedural interpreter marker; never executed.\n'

    def archive(self, extra=()):
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode='w:gz', format=tarfile.PAX_FORMAT) as archive:
            executable = tarfile.TarInfo('python/bin/python3.13')
            executable.mode = 0o755
            executable.size = len(self.payload)
            archive.addfile(executable, io.BytesIO(self.payload))
            for member, data in extra:
                archive.addfile(member, io.BytesIO(data) if data is not None else None)
        return output.getvalue()

    @staticmethod
    def file(name, data=b'public procedural library\n', **attributes):
        member = tarfile.TarInfo(name)
        member.mode = 0o644
        member.size = len(data)
        for name, value in attributes.items():
            setattr(member, name, value)
        return member, data

    @staticmethod
    def link(name, target, kind=tarfile.SYMTYPE):
        member = tarfile.TarInfo(name)
        member.type = kind
        member.linkname = target
        return member, None

    def reviewed(self, data):
        return patch.multiple(installer, ARCHIVE_BYTES=len(data),
                              ARCHIVE_SHA256=hashlib.sha256(data).hexdigest())

    @unittest.skipUnless(sys.platform == 'linux', 'Native Linux fd-relative extraction contract')
    def test_valid_cache_is_checked_and_extracted_without_network_or_execution(self):
        data = self.archive((self.file('python/lib/public.so'),
                             self.link('python/bin/python3', 'python3.13')))
        self.cache.mkdir()
        cached = self.cache / installer.ARCHIVE_NAME
        cached.write_bytes(data)
        with self.reviewed(data), patch.object(installer.urllib.request, 'urlopen') as network, \
                patch('subprocess.Popen', side_effect=AssertionError('No downloaded program execution')):
            executable = installer.install(self.destination, self.cache)
        network.assert_not_called()
        self.assertEqual(executable, self.destination / 'python/bin/python3.13')
        self.assertEqual(executable.read_bytes(), self.payload)
        self.assertEqual(stat.S_IMODE(executable.stat().st_mode), 0o755)
        self.assertEqual((self.destination / 'python/lib/public.so').read_bytes(), b'public procedural library\n')
        self.assertEqual(os.readlink(self.destination / 'python/bin/python3'), 'python3.13')
        self.assertEqual(cached.read_bytes(), data)

    @unittest.skipUnless(sys.platform == 'linux', 'Native Linux fd-relative extraction contract')
    def test_corrupt_cache_refuses_without_redownload_or_destination_creation(self):
        data = self.archive()
        self.cache.mkdir()
        cached = self.cache / installer.ARCHIVE_NAME
        corrupted = data[:-1] + bytes([data[-1] ^ 1])
        cached.write_bytes(corrupted)
        with self.reviewed(data), patch.object(installer.urllib.request, 'urlopen') as network:
            with self.assertRaisesRegex(ValueError, 'reviewed SHA-256'):
                installer.install(self.destination, self.cache)
        network.assert_not_called()
        self.assertFalse(self.destination.exists())
        self.assertEqual(cached.read_bytes(), corrupted)

    @unittest.skipUnless(sys.platform == 'linux', 'Native Linux fd-relative extraction contract')
    def test_download_is_bounded_and_authenticated_before_cache_or_extraction(self):
        data = self.archive()
        response = io.BytesIO(data + b'foreign trailing data')
        with self.reviewed(data), patch.object(response, 'read', wraps=response.read) as read, \
                patch.object(installer.urllib.request, 'urlopen', return_value=response) as network:
            with self.assertRaisesRegex(ValueError, 'reviewed SHA-256'):
                installer.install(self.destination, self.cache)
        network.assert_called_once_with(installer.ARCHIVE_URL, timeout=30)
        read.assert_called_once_with(len(data) + 1)
        self.assertFalse((self.cache / installer.ARCHIVE_NAME).exists())
        self.assertFalse(self.destination.exists())
        # An authenticated fresh archive is cached exactly; it is never launched.
        with self.reviewed(data), patch.object(installer.urllib.request, 'urlopen', return_value=io.BytesIO(data)), \
                patch('subprocess.Popen', side_effect=AssertionError('No downloaded program execution')):
            installer.install(self.destination, self.cache)
        self.assertEqual((self.cache / installer.ARCHIVE_NAME).read_bytes(), data)

    def test_unsafe_archive_members_are_rejected_before_destination_creation(self):
        fifo = tarfile.TarInfo('python/pipe')
        fifo.type = tarfile.FIFOTYPE
        cases = {
            'traversal': (self.file('python/../escape'),),
            'absolute': (self.file('/absolute'),),
            'backslash': (self.file('python\\escape'),),
            'duplicate': (self.file('python/bin/python3.13'),),
            'hardlink': (self.link('python/bin/hard', 'python/bin/python3.13', tarfile.LNKTYPE),),
            'special': ((fifo, None),),
            'setuid': (self.file('python/bin/unsafe', mode=0o4755),),
            'pax-metadata': (self.file('python/public', pax_headers={'comment': 'unsupported'}),),
            'escaping-link': (self.link('python/bin/python3', '../../../escape'),),
            'absolute-link': (self.link('python/bin/python3', '/absolute'),),
            'dangling-link': (self.link('python/bin/python3', 'missing'),),
            'link-cycle': (self.link('python/bin/a', 'b'), self.link('python/bin/b', 'a')),
            'link-ancestor': (self.link('python/lib', 'bin'), self.file('python/lib/child')),
        }
        for name, members in cases.items():
            with self.subTest(name=name):
                data = self.archive(members)
                with self.reviewed(data), self.assertRaises((ValueError, tarfile.TarError)):
                    installer._validated_members(data)
                self.assertFalse(self.destination.exists())
                self.assertEqual(list(self.work.iterdir()), [])

    def test_archive_and_member_resource_bounds_are_enforced_before_creation(self):
        data = self.archive((self.file('python/public', b'x' * 128),))
        for limits in ({'ARCHIVE_BYTES': len(data) - 1}, {'MAX_TAR_BYTES': 1024},
                       {'MAX_MEMBERS': 1}, {'MAX_FILE_BYTES': 100}):
            with self.subTest(limits=limits), patch.multiple(installer, **limits):
                with self.assertRaises(ValueError):
                    installer._validated_members(data)
            self.assertFalse(self.destination.exists())
        for bad in (b'not gzip', data + data):
            with self.subTest(format=bad[:8]), self.assertRaises((ValueError, tarfile.TarError)):
                installer._validated_members(bad)
            self.assertFalse(self.destination.exists())

    def test_exact_reviewed_length_and_digest_are_required_on_every_host(self):
        data = self.archive()
        with self.reviewed(data):
            self.assertIs(installer._verified(data), data)
            for bad in (data[:-1], data + b'\0', data[:-1] + bytes([data[-1] ^ 1])):
                with self.subTest(length=len(bad)), self.assertRaisesRegex(ValueError, 'reviewed SHA-256'):
                    installer._verified(bad)

    @unittest.skipUnless(sys.platform == 'linux', 'Native Linux fd-relative extraction contract')
    def test_existing_destination_and_selected_alias_preserve_originals(self):
        data = self.archive()
        self.destination.mkdir()
        source = self.destination / 'original'
        source.write_bytes(b'preserve original')
        with self.reviewed(data), patch.object(installer.urllib.request, 'urlopen') as network:
            with self.assertRaises(FileExistsError):
                installer.install(self.destination, self.cache)
        network.assert_not_called()
        self.assertEqual(source.read_bytes(), b'preserve original')
        source.unlink()
        self.destination.rmdir()
        outside = self.root / 'outside'
        outside.mkdir()
        self.destination.symlink_to(outside, target_is_directory=True)
        with self.reviewed(data), self.assertRaises(ValueError):
            installer._extract(data, self.destination)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertTrue(self.destination.is_symlink())

    @unittest.skipUnless(sys.platform == 'linux', 'Native Linux fd-relative extraction contract')
    def test_replaced_parent_cannot_redirect_anchored_extraction(self):
        data = self.archive()
        parent = self.work / 'parent'
        parent.mkdir()
        selected = parent / 'new'
        held = self.work / 'retained-parent'
        outside = self.root / 'outside'
        outside.mkdir()
        sentinel = outside / 'original'
        sentinel.write_bytes(b'preserve original')
        mkdir = os.mkdir
        replaced = False

        def replace_parent(name, *args, **kwargs):
            nonlocal replaced
            if name == 'new' and kwargs.get('dir_fd') is not None and not replaced:
                replaced = True
                parent.rename(held)
                parent.symlink_to(outside, target_is_directory=True)
            return mkdir(name, *args, **kwargs)

        with self.reviewed(data), patch.object(installer.os, 'mkdir', side_effect=replace_parent):
            with self.assertRaises((ValueError, OSError)):
                installer._extract(data, selected)
        self.assertTrue(replaced)
        self.assertEqual(list(outside.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_bytes(), b'preserve original')
        self.assertFalse((outside / 'new').exists())

    @unittest.skipUnless(sys.platform == 'linux', 'Native Linux fd-relative extraction contract')
    def test_ancestor_alias_and_outside_work_selection_are_refused(self):
        data = self.archive()
        outside = self.root / 'outside'
        outside.mkdir()
        alias = self.work / 'alias'
        alias.symlink_to(outside, target_is_directory=True)
        for selected in (alias / 'new', outside / 'new', self.work):
            with self.subTest(selected=selected.name), self.reviewed(data), self.assertRaises(ValueError):
                installer._extract(data, selected)
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
