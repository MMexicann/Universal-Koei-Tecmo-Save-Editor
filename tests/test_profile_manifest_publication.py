"""Profile manifests publish exact verified bytes without replacing existing data."""
import os
import ctypes
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import copy_storage


@unittest.skipUnless(os.name == 'nt' or sys.platform.startswith('linux'),
                     'Handle-bound manifest publication supports Windows and Linux.')
class ProfileManifestPublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.directory = self.root / 'private-store'
        self.directory.mkdir(mode=0o700)
        info = self.directory.stat()
        self.identity = info.st_dev, info.st_ino

    def test_published_ascii_unicode_empty_and_short_names_have_exact_bytes_and_are_exclusive(self):
        for name, data in (('component.json', b'{"inert":true}'),
                           ('r\u00e9sum\u00e9-\U0001f3ae.json', bytes(range(256)) * 600),
                           ('empty.json', b''), ('a', b'short-name')):
            with self.subTest(name=name):
                result = copy_storage.publish_new_child_bound(data, self.directory, name, self.identity)
                self.assertEqual(result, self.directory / name)
                self.assertEqual(result.read_bytes(), data)
                self.assertEqual(result.stat().st_nlink, 1)
                if os.name == 'posix':
                    self.assertEqual(stat.S_IMODE(result.stat().st_mode), 0o600)
                with self.assertRaises(SaveError) as caught:
                    copy_storage.publish_new_child_bound(
                        b'preserve existing', self.directory, name, self.identity)
                self.assertNotIsInstance(caught.exception, copy_storage.ChildPublishedUncertainError)
                self.assertEqual(result.read_bytes(), data)

    def test_wrong_parent_identity_never_creates_a_manifest(self):
        with self.assertRaises(SaveError):
            copy_storage.publish_new_child_bound(
                b'inert profile', self.directory, 'profile.json',
                (self.identity[0], self.identity[1] + 1))
        self.assertEqual(tuple(self.directory.iterdir()), ())

    def test_interrupted_native_publication_return_retains_complete_manifest_and_reports_uncertainty(self):
        data = b'exact inert manifest after interrupted native return'
        if os.name == 'nt':
            original_rename = copy_storage._rename_verified_child_windows

            def interrupt_after_rename(*args):
                status = original_rename(*args)
                if status >= 0:
                    raise KeyboardInterrupt('native rename committed before Python received its return')
                return status

            native_call = patch.object(copy_storage, '_rename_verified_child_windows',
                                       side_effect=interrupt_after_rename)
        else:
            library = ctypes.CDLL(None, use_errno=True)
            linkat = library.linkat
            linkat.argtypes = [ctypes.c_int, ctypes.c_char_p,
                               ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
            linkat.restype = ctypes.c_int

            class InterruptedLink:
                def __call__(self, *args):
                    status = linkat(*args)
                    if status == 0:
                        raise KeyboardInterrupt('native link committed before Python received its return')
                    return status

            native_call = patch.object(ctypes, 'CDLL',
                                       return_value=SimpleNamespace(linkat=InterruptedLink()))

        with native_call, self.assertRaises(copy_storage.ChildPublishedUncertainError) as caught:
            copy_storage.publish_new_child_bound(data, self.directory, 'manifest.json', self.identity)
        self.assertEqual(caught.exception.destination, self.directory / 'manifest.json')
        self.assertEqual((self.directory / 'manifest.json').read_bytes(), data)
        self.assertEqual(tuple(self.directory.iterdir()), (self.directory / 'manifest.json',))

    @unittest.skipUnless(os.name == 'posix', 'POSIX created-inode read-back coverage')
    def test_bound_child_rejects_same_bytes_replacement_before_reading_foreign_inode(self):
        data = b'exact generated component bytes'
        destination = self.directory / 'component.json'
        displaced = self.directory / 'created-inode'
        original_open = os.open
        injected = False

        def replace_before_verify(name, flags, *args, **kwargs):
            nonlocal injected
            if name == destination.name and not flags & os.O_CREAT:
                destination.rename(displaced)
                destination.write_bytes(data)
                injected = True
            return original_open(name, flags, *args, **kwargs)

        with patch.object(copy_storage.os, 'open', side_effect=replace_before_verify), \
                patch.object(copy_storage.os, 'read',
                             side_effect=AssertionError('Do not read a replacement inode')):
            with self.assertRaisesRegex(SaveError, 'created ordinary file'):
                copy_storage.new_child_bound(data, self.directory, destination.name, self.identity)
        self.assertTrue(injected)
        self.assertEqual(destination.read_bytes(), data)
        self.assertEqual(displaced.read_bytes(), data)
        self.assertNotEqual(destination.stat().st_ino, displaced.stat().st_ino)


if __name__ == '__main__':
    unittest.main()
