"""Exclusive copy publication must verify only its owned, bounded staging file."""
from contextlib import contextmanager
import os
from pathlib import Path
import stat
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
        self.folder = Path(temporary.name)
        self.destination = self.folder / 'copy.bin'
        self.staging = self.folder / '.copy.bin.owned-test.tmp'
        self.uuid_patch = patch.object(copy_storage.uuid, 'uuid4', return_value=SimpleNamespace(hex='owned-test'))
        self.uuid_patch.start()
        self.addCleanup(self.uuid_patch.stop)

    def test_success_uses_one_bounded_read_on_owned_handle_and_preserves_mode(self):
        content = b'bounded synthetic copy'
        original_open = open
        reads = []

        @contextmanager
        def track_open(*args, **kwargs):
            with original_open(*args, **kwargs) as stream:
                class Tracked:
                    def __getattr__(self, name):
                        return getattr(stream, name)

                    def read(self, size):
                        reads.append(size)
                        return stream.read(size)
                yield Tracked()

        with patch.object(copy_storage, 'open', track_open, create=True), \
                patch.object(Path, 'read_bytes', side_effect=AssertionError('No path reopen for verification')):
            result = copy_storage.atomic_new(content, self.destination, mode=0o600)
        self.assertEqual(result, self.destination)
        self.assertEqual(self.destination.read_bytes(), content)
        self.assertEqual(reads, [len(content) + 1])
        self.assertFalse(self.staging.exists())
        if os.name == 'posix':
            self.assertEqual(stat.S_IMODE(self.destination.stat().st_mode), 0o600)

    def test_foreign_staging_replacement_is_never_read_published_or_removed(self):
        foreign = self.folder / 'outside-private.bin'
        foreign.write_bytes(b'SYNTHETIC_PRIVATE_CONTENT')
        original_fsync = os.fsync

        def replace_staging(descriptor):
            original_fsync(descriptor)
            # Windows denies replacing an open CRT file; inject after close is
            # unnecessary there because the held handle already excludes this race.
            try:
                self.staging.unlink()
                self.staging.symlink_to(foreign)
            except PermissionError:
                self.skipTest('Runtime denies replacing open staging files')
            except OSError:
                self.skipTest('File symlinks unavailable')

        with patch.object(copy_storage.os, 'fsync', replace_staging), \
                patch.object(Path, 'read_bytes', side_effect=AssertionError('Foreign path must not be read')):
            with self.assertRaises(SaveError):
                copy_storage.atomic_new(b'owned bytes', self.destination)
        self.assertTrue(self.staging.is_symlink())
        self.assertEqual(foreign.read_bytes(), b'SYNTHETIC_PRIVATE_CONTENT')
        self.assertFalse(self.destination.exists())

    def test_write_failure_cleanup_preserves_foreign_staging_file(self):
        original_fsync = os.fsync

        def replace_and_fail(descriptor):
            original_fsync(descriptor)
            try:
                self.staging.unlink()
            except PermissionError:
                self.skipTest('Runtime denies replacing open staging files')
            self.staging.write_bytes(b'FOREIGN_STAGING_FILE')
            raise OSError('synthetic sync failure')

        with patch.object(copy_storage.os, 'fsync', replace_and_fail):
            with self.assertRaises(OSError):
                copy_storage.atomic_new(b'owned bytes', self.destination)
        self.assertEqual(self.staging.read_bytes(), b'FOREIGN_STAGING_FILE')
        self.assertFalse(self.destination.exists())

    def test_concurrent_destination_is_preserved_and_owned_staging_is_removed(self):
        original_fsync = os.fsync

        def occupy_destination(descriptor):
            original_fsync(descriptor)
            self.destination.write_bytes(b'FOREIGN_DESTINATION')

        with patch.object(copy_storage.os, 'fsync', occupy_destination):
            with self.assertRaises(FileExistsError):
                copy_storage.atomic_new(b'owned bytes', self.destination)
        self.assertEqual(self.destination.read_bytes(), b'FOREIGN_DESTINATION')
        self.assertFalse(self.staging.exists())

    def test_existing_destination_is_never_overwritten(self):
        self.destination.write_bytes(b'keep existing')
        with self.assertRaises(FileExistsError):
            copy_storage.atomic_new(b'new bytes', self.destination)
        self.assertEqual(self.destination.read_bytes(), b'keep existing')
        self.assertFalse(self.staging.exists())


if __name__ == '__main__':
    unittest.main()
