"""Exclusive copy publication must verify only its owned, bounded staging file."""
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import copy_storage


class AtomicNewSafetyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        # Windows TemporaryDirectory may use an 8.3 alias; storage returns a
        # canonical path. Resolve the existing parent before creating children.
        self.folder = Path(temporary.name).resolve()
        self.destination = self.folder / 'copy.bin'
        self.staging = self.folder / '.copy.bin.owned-test.tmp'
        self.uuid_patch = patch.object(copy_storage.uuid, 'uuid4', return_value=SimpleNamespace(hex='owned-test'))
        self.uuid_patch.start()
        self.addCleanup(self.uuid_patch.stop)

    @unittest.skipUnless(os.name == 'nt' or sys.platform.startswith('linux'),
                         'Safe new-file publication is supported on Windows and Linux')
    def test_success_publishes_exact_bytes_without_path_read_and_preserves_mode(self):
        content = b'bounded synthetic copy'
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('No path reopen for verification')):
            result = copy_storage.atomic_new(content, self.destination, mode=0o600)
        self.assertEqual(result, self.destination)
        self.assertEqual(self.destination.read_bytes(), content)
        self.assertFalse(self.staging.exists())
        if os.name == 'posix':
            self.assertEqual(stat.S_IMODE(self.destination.stat().st_mode), 0o600)

    @unittest.skipUnless(os.name == 'nt', 'Linux publication uses an unnamed staging inode')
    def test_foreign_staging_replacement_is_never_read_published_or_removed(self):
        expected = b'owned profile report bytes'
        foreign = b'FOREIGN_STAGING_CONTENT'
        injected = []
        original_rename = os.rename

        def replace_staging_then_rename(source, destination):
            self.staging.unlink()
            self.staging.write_bytes(foreign)
            injected.append(True)
            return original_rename(source, destination)

        with patch.object(copy_storage.os, 'rename', side_effect=replace_staging_then_rename):
            result = copy_storage.atomic_new(expected, self.destination)
        self.assertEqual(result.read_bytes(), expected)
        self.assertEqual(injected, [])
        self.assertFalse(self.staging.exists())

    @unittest.skipUnless(sys.platform.startswith('linux'),
                         'Unnamed staging publication is Linux-specific')
    def test_staging_path_replacement_at_publication_never_publishes_foreign_bytes(self):
        expected = b'owned profile report bytes'
        foreign = b'FOREIGN_STAGING_CONTENT'
        injected = []

        original_link = os.link

        def replace_staging_then_link(source, destination, *, follow_symlinks=True):
            self.staging.unlink()
            self.staging.write_bytes(foreign)
            injected.append(True)
            return original_link(source, destination, follow_symlinks=follow_symlinks)

        with patch.object(copy_storage.os, 'link', side_effect=replace_staging_then_link):
            result = copy_storage.atomic_new(expected, self.destination)
        self.assertEqual(result.read_bytes(), expected)
        self.assertEqual(injected, [])
        self.assertFalse(self.staging.exists())

    @unittest.skipUnless(sys.platform.startswith('linux'),
                         'Unnamed staging publication is Linux-specific')
    def test_sync_failure_never_publishes_an_unnamed_output(self):
        with patch.object(copy_storage.os, 'fsync', side_effect=OSError('synthetic sync failure')):
            with self.assertRaisesRegex(OSError, 'synthetic sync failure'):
                copy_storage.atomic_new(b'owned bytes', self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual(tuple(self.folder.iterdir()), ())

    def test_concurrent_destination_is_preserved_and_owned_staging_is_removed(self):
        def occupy_destination(*args):
            self.destination.write_bytes(b'FOREIGN_DESTINATION')
            return -1073741771  # STATUS_OBJECT_NAME_COLLISION

        if os.name == 'nt':
            with patch.object(copy_storage, '_rename_verified_child_windows',
                              side_effect=occupy_destination):
                with self.assertRaises(FileExistsError):
                    copy_storage.atomic_new(b'owned bytes', self.destination)
        elif sys.platform.startswith('linux'):
            original_fsync = os.fsync

            def occupy_during_sync(descriptor):
                original_fsync(descriptor)
                self.destination.write_bytes(b'FOREIGN_DESTINATION')

            with patch.object(copy_storage.os, 'fsync', occupy_during_sync):
                with self.assertRaises(FileExistsError):
                    copy_storage.atomic_new(b'owned bytes', self.destination)
        else:
            with self.assertRaises(SaveError):
                copy_storage.atomic_new(b'owned bytes', self.destination)
            self.assertFalse(self.destination.exists())
            self.assertEqual(tuple(self.folder.iterdir()), ())
            return
        self.assertEqual(self.destination.read_bytes(), b'FOREIGN_DESTINATION')
        self.assertFalse(self.staging.exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows handle-bound cleanup coverage')
    def test_failed_windows_publication_removes_owned_pending_file(self):
        with patch.object(copy_storage, '_rename_verified_child_windows',
                          return_value=-1073741823):
            with self.assertRaises(SaveError):
                copy_storage.atomic_new(b'owned bytes', self.destination)
        self.assertFalse(self.destination.exists())
        self.assertFalse(self.staging.exists())

    def test_existing_destination_is_never_overwritten(self):
        self.destination.write_bytes(b'keep existing')
        with self.assertRaises(FileExistsError):
            copy_storage.atomic_new(b'new bytes', self.destination)
        self.assertEqual(self.destination.read_bytes(), b'keep existing')
        self.assertFalse(self.staging.exists())


if __name__ == '__main__':
    unittest.main()
