"""Late-copy failures retain files and never report mismatched PS3 exports as success."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.wo3u_ps3 import parser
from koei_editor.shared import copy_storage
from tests.test_wo3u_ps3 import fixture, metadata


class WO3PS3CopyRaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.source = self.folder / 'copy.bin'
        self.source.write_bytes(fixture())
        self.companion = self.folder / 'PARAM.SFO'
        self.companion.write_bytes(metadata())
        self.document = parser.read_save(self.source)
        self.destination = self.folder / 'edited.bin'

    def _mutate(self, path):
        raw = path.read_bytes()
        changed = raw[:-1] + bytes((raw[-1] ^ 1,))
        path.write_bytes(changed)
        return changed

    def _late_created(self, mutation):
        original = parser.atomic_new
        calls = []
        def create(raw, path):
            result = original(raw, path)
            # On Windows a temporary-directory alias may be canonicalized.
            # Compare the created file identity, not the path spelling.
            if self.destination.exists() and Path(path).samefile(self.destination):
                mutation()
                calls.append(path)
            return result
        with patch.object(parser, 'atomic_new', side_effect=create):
            with self.assertRaises(SaveError):
                parser.save_as(self.document, {'gems': 321}, self.destination)
        self.assertEqual(len(calls), 1)
        self.assertTrue(self.destination.exists())
        snapshots = list((self.folder / 'UniversalEditorBackups').glob('*.bin'))
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].read_bytes(), self.document.raw)
        self.assertTrue(snapshots[0].with_suffix('.json').is_file())

    def test_context_mutation_after_creation_retains_completed_output_and_backup(self):
        self._late_created(lambda: self.companion.write_bytes(metadata() + b'opaque context change'))
        self.assertEqual(self.source.read_bytes(), self.document.raw)
        self.assertEqual(self.destination.read_bytes(), parser.serialize(self.document, {'gems': 321}))

    def test_source_mutation_after_creation_is_not_accepted(self):
        self._late_created(lambda: self._mutate(self.source))
        self.assertNotEqual(self.source.read_bytes(), self.document.raw)
        self.assertEqual(self.destination.read_bytes(), parser.serialize(self.document, {'gems': 321}))

    def test_foreign_destination_replacement_before_actual_readback_is_retained(self):
        foreign = []
        self._late_created(lambda: foreign.append(self._mutate(self.destination)))
        self.assertEqual(self.destination.read_bytes(), foreign[0])
        self.assertEqual(self.source.read_bytes(), self.document.raw)

    def test_context_mutation_after_actual_readback_is_not_accepted(self):
        original = parser.read_save
        injections = []
        def read(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if self.destination.exists() and Path(path).samefile(self.destination):
                self.companion.write_bytes(metadata() + b'changed after read')
                injections.append(path)
            return result
        with patch.object(parser, 'read_save', side_effect=read):
            with self.assertRaises(SaveError):
                parser.save_as(self.document, {'gems': 321}, self.destination)
        self.assertEqual(len(injections), 1)
        self.assertTrue(self.destination.is_file())
        self.assertEqual(self.source.read_bytes(), self.document.raw)

    def test_backup_rejects_stale_source_before_creation(self):
        self._mutate(self.source)
        with self.assertRaises(SaveError):
            parser.backup(self.document)
        self.assertFalse((self.folder / 'UniversalEditorBackups').exists())

    def test_context_preparation_rejects_changed_gameplay_source(self):
        self._mutate(self.source)
        output = self.folder / 'private-copy'
        with self.assertRaises(SaveError):
            parser.prepare_copy_context(self.document, output)
        self.assertFalse(output.exists())

    def test_context_preparation_retains_created_context_on_late_failure(self):
        original = parser.atomic_new
        output = self.folder / 'private-copy'
        created = []
        def create(raw, path):
            result = original(raw, path)
            self.companion.write_bytes(metadata() + b'changed during preparation')
            created.append(result)
            return result
        with patch.object(parser, 'atomic_new', side_effect=create):
            with self.assertRaises(SaveError):
                parser.prepare_copy_context(self.document, output)
        self.assertEqual(len(created), 1)
        self.assertEqual((output / 'PARAM.SFO').read_bytes(), metadata())

    def test_backup_retains_completed_snapshot_when_context_changes_late(self):
        original = parser.snapshot_backup
        created = []
        def snapshot(*args, **kwargs):
            result = original(*args, **kwargs)
            created.append(result)
            self.companion.write_bytes(metadata() + b'changed during backup')
            return result
        with patch.object(parser, 'snapshot_backup', side_effect=snapshot):
            with self.assertRaises(SaveError):
                parser.backup(self.document)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].read_bytes(), self.document.raw)
        self.assertTrue(created[0].with_suffix('.json').is_file())

    def test_restore_context_mutation_after_atomic_creation_is_rejected_and_retained(self):
        snapshot = parser.backup(self.document)
        original = copy_storage.atomic_new
        injections = []
        def create(raw, path):
            result = original(raw, path)
            if self.destination.exists() and Path(path).samefile(self.destination):
                self.companion.write_bytes(metadata() + b'changed during restore')
                injections.append(path)
            return result
        with patch.object(copy_storage, 'atomic_new', side_effect=create):
            with self.assertRaises(SaveError):
                parser.restore(snapshot, self.destination)
        self.assertEqual(len(injections), 1)
        self.assertEqual(self.destination.read_bytes(), self.document.raw)
        self.assertEqual(snapshot.read_bytes(), self.document.raw)

    def test_restore_foreign_output_is_detected_without_deleting_it(self):
        snapshot = parser.backup(self.document)
        original = copy_storage.atomic_new
        foreign = []
        def create(raw, path):
            result = original(raw, path)
            if self.destination.exists() and Path(path).samefile(self.destination):
                foreign.append(self._mutate(self.destination))
            return result
        with patch.object(copy_storage, 'atomic_new', side_effect=create):
            with self.assertRaises(SaveError):
                parser.restore(snapshot, self.destination)
        self.assertEqual(len(foreign), 1)
        self.assertEqual(self.destination.read_bytes(), foreign[0])
        self.assertEqual(snapshot.read_bytes(), self.document.raw)
