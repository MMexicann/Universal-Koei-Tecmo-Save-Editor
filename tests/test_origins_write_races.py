"""Origins copy writes reject source drift and verify actual destination bytes."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.origins import origins_parser as backend
from tests.test_origins_parser import fixture


class OriginsWriteRaceTests(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory()
        self.addCleanup(self.area.cleanup)
        self.folder = Path(self.area.name)
        self.source = self.folder / "opened.dat"
        self.source.write_bytes(fixture())
        self.document = backend.read_save(self.source)
        self.target = self.folder / "edited.dat"
        self.pending = {"gold": 321}

    def test_backup_rejects_source_drift_before_creating_any_files(self):
        self.source.write_bytes(b"changed by another process")
        with self.assertRaises(SaveError):
            backend.backup(self.document)
        self.assertFalse((self.folder / "WarriorsEditorBackups").exists())
        self.assertEqual(self.source.read_bytes(), b"changed by another process")

    def test_source_drift_during_serialization_refuses_output(self):
        real = backend.serialize

        def serialize(*args):
            raw = real(*args)
            self.source.write_bytes(b"new source state")
            return raw

        with (
            patch.object(backend, "serialize", side_effect=serialize),
            self.assertRaises(SaveError),
        ):
            backend.save_as(self.document, self.pending, self.target)
        self.assertFalse(self.target.exists())
        self.assertEqual(self.source.read_bytes(), b"new source state")

    def test_source_drift_after_atomic_creation_retains_the_completed_output(self):
        real = backend.atomic_new
        expected = backend.serialize(self.document, self.pending)

        def write(raw, destination):
            result = real(raw, destination)
            self.source.write_bytes(b"new source state")
            return result

        with (
            patch.object(backend, "atomic_new", side_effect=write),
            self.assertRaises(SaveError),
        ):
            backend.save_as(self.document, self.pending, self.target)
        self.assertEqual(self.target.read_bytes(), expected)
        self.assertEqual(self.source.read_bytes(), b"new source state")
        backups = list((self.folder / "WarriorsEditorBackups").glob("*.dat"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), self.document.raw)

    def test_late_failure_never_opens_a_destination_cleanup_deletion_window(self):
        real_write, real_unlink = backend.atomic_new, Path.unlink
        expected = backend.serialize(self.document, self.pending)
        deletion_attempts = []

        def write(raw, destination):
            result = real_write(raw, destination)
            self.source.write_bytes(b'new source state')
            return result

        def replace_between_comparison_and_unlink(path, *args, **kwargs):
            if path == self.target:
                # The previous cleanup compared the original bytes before
                # calling unlink. Replace them in exactly that deletion gap.
                path.write_bytes(b'another application replaced this output')
                deletion_attempts.append(path)
            return real_unlink(path, *args, **kwargs)

        with (
            patch.object(backend, 'atomic_new', side_effect=write),
            patch.object(Path, 'unlink', replace_between_comparison_and_unlink),
            self.assertRaises(SaveError),
        ):
            backend.save_as(self.document, self.pending, self.target)
        self.assertEqual(deletion_attempts, [])
        self.assertEqual(self.target.read_bytes(), expected)
        self.assertEqual(self.source.read_bytes(), b'new source state')

    def test_source_drift_after_destination_readback_retains_the_completed_output(self):
        read = backend.read_save
        expected = backend.serialize(self.document, self.pending)

        def change_after_readback(path, *args, **kwargs):
            reopened = read(path, *args, **kwargs)
            self.source.write_bytes(b'new source state after read-back')
            return reopened

        with (
            patch.object(backend, 'read_save', side_effect=change_after_readback),
            self.assertRaises(SaveError),
        ):
            backend.save_as(self.document, self.pending, self.target)
        self.assertEqual(self.target.read_bytes(), expected)
        self.assertEqual(self.source.read_bytes(), b'new source state after read-back')

    def test_actual_destination_corruption_is_rejected_and_retained(self):
        real = backend.atomic_new
        foreign = b"changed destination"

        def write(raw, destination):
            result = real(raw, destination)
            Path(destination).write_bytes(foreign)
            return result

        with (
            patch.object(backend, "atomic_new", side_effect=write),
            self.assertRaises(SaveError),
        ):
            backend.save_as(self.document, self.pending, self.target)
        self.assertEqual(self.target.read_bytes(), foreign)
        self.assertEqual(self.source.read_bytes(), self.document.raw)

    def test_valid_native_replacement_is_not_accepted_as_the_requested_output(self):
        real = backend.atomic_new
        foreign = fixture(gold=777)

        def write(raw, destination):
            result = real(raw, destination)
            Path(destination).write_bytes(foreign)
            return result

        with (
            patch.object(backend, "atomic_new", side_effect=write),
            self.assertRaises(SaveError),
        ):
            backend.save_as(self.document, self.pending, self.target)
        self.assertEqual(self.target.read_bytes(), foreign)
        self.assertEqual(self.source.read_bytes(), self.document.raw)

    def test_source_drift_during_backup_is_detected_after_snapshot_creation(self):
        real = backend.snapshot_backup

        def snapshot(*args):
            result = real(*args)
            self.source.write_bytes(b"new source state")
            return result

        with (
            patch.object(backend, "snapshot_backup", side_effect=snapshot),
            self.assertRaises(SaveError),
        ):
            backend.backup(self.document)
        backups = list((self.folder / "WarriorsEditorBackups").glob("*.dat"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), self.document.raw)
        self.assertEqual(self.source.read_bytes(), b"new source state")

    def test_valid_new_copy_reopens_and_existing_destination_is_preserved(self):
        result = backend.save_as(self.document, self.pending, self.target)
        self.assertEqual(result.raw, self.target.read_bytes())
        self.assertEqual(backend.field_map(result)["gold"].value(result.payload), 321)
        before = self.target.read_bytes()
        with self.assertRaises(FileExistsError):
            backend.save_as(self.document, {"gold": 999}, self.target)
        self.assertEqual(self.target.read_bytes(), before)
        self.assertEqual(self.source.read_bytes(), self.document.raw)


if __name__ == "__main__":
    unittest.main()
