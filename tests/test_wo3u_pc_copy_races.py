"""Native WO3 PC copies fail closed on source and created-file changes."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.wo3u import wo3u_parser as p
from koei_editor.game_registry import get_game
from tests.test_wo3u_format import procedural_raw


class WO3PCCopyRaceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.source = self.folder / 'SAVEDATA.BIN'
        self.source.write_bytes(procedural_raw())
        self.document = p.read_save(self.source)
        self.destination = self.folder / 'edited.bin'
        self.expected = p.serialize(self.document, {'gems': 321})

    def mutate(self, path):
        raw = path.read_bytes()
        changed = raw[:-1] + bytes((raw[-1] ^ 1,))
        path.write_bytes(changed)
        return changed

    def snapshots(self):
        return list((self.folder / 'WarriorsEditorBackups').glob('*'))

    def test_stale_or_unavailable_sources_never_create_backups(self):
        self.mutate(self.source)
        with self.assertRaises(SaveError):
            p.backup(self.document)
        self.assertEqual(self.snapshots(), [])
        self.source.unlink()
        with self.assertRaises(SaveError):
            p.backup(self.document)
        self.assertEqual(self.snapshots(), [])

    def test_source_change_during_serialization_never_creates_backup_or_output(self):
        serialize = p.serialize
        def changed(document, changes):
            result = serialize(document, changes)
            self.mutate(self.source)
            return result
        with patch.object(p, 'serialize', side_effect=changed), self.assertRaises(SaveError):
            p.save_as(self.document, {'gems': 321}, self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.snapshots(), [])

    def test_source_change_during_snapshot_creation_is_rejected_and_completed_backup_retained(self):
        snapshot = p.snapshot_backup
        created = []
        def changed(*args, **kwargs):
            result = snapshot(*args, **kwargs)
            created.append(result)
            self.mutate(self.source)
            return result
        with patch.object(p, 'snapshot_backup', side_effect=changed), self.assertRaises(SaveError):
            p.backup(self.document)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].read_bytes(), self.document.raw)
        self.assertTrue(created[0].with_suffix('.json').is_file())
        self.assertNotEqual(self.source.read_bytes(), self.document.raw)

    def test_source_change_after_backup_prevents_direct_scalar_save(self):
        backup = p.backup
        created = []
        def changed(document):
            result = backup(document)
            created.append(result)
            self.mutate(self.source)
            return result
        adapter = get_game(p.GAME_ID).get_scalar_adapter()
        with patch.object(p, 'backup', side_effect=changed), self.assertRaises(SaveError):
            adapter.save_as(self.document, {'gems': 321}, self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual(created[0].read_bytes(), self.document.raw)
        self.assertNotEqual(self.source.read_bytes(), self.document.raw)

    def test_backup_verifies_raw_and_bounded_manifest_without_removing_replacements(self):
        for target in ('raw', 'manifest', 'oversized manifest', 'wrong hash', 'wrong size', 'wrong game', 'wrong kind'):
            with self.subTest(target=target):
                original = p.snapshot_backup
                observed = {}
                def replaced(*args, **kwargs):
                    result = original(*args, **kwargs)
                    manifest_path = result.with_suffix('.json')
                    if target == 'raw':
                        path, raw = result, b'foreign replacement'
                    elif target == 'manifest':
                        path, raw = manifest_path, b'{'
                    elif target == 'oversized manifest':
                        path, raw = manifest_path, b' ' * 4097
                    else:
                        manifest = json.loads(manifest_path.read_bytes())
                        key, value = {'wrong hash': ('sha256', '0' * 64),
                                      'wrong size': ('size_bytes', p.SAVE_SIZE - 1),
                                      'wrong game': ('game_id', 'wo3u_ps3'),
                                      'wrong kind': ('kind', 'other')}[target]
                        manifest[key] = value
                        path, raw = manifest_path, json.dumps(manifest).encode()
                    path.write_bytes(raw)
                    observed.update(path=path, raw=raw, result=result)
                    return result
                with patch.object(p, 'snapshot_backup', side_effect=replaced), self.assertRaises(SaveError):
                    p.backup(self.document)
                self.assertEqual(observed['path'].read_bytes(), observed['raw'])
                self.assertTrue(observed['result'].exists())
                self.assertTrue(observed['result'].with_suffix('.json').exists())
                self.assertEqual(self.source.read_bytes(), self.document.raw)

    def test_source_change_after_atomic_write_is_rejected_without_deleting_output(self):
        atomic = p.atomic_new
        def changed(raw, destination):
            result = atomic(raw, destination)
            if Path(destination).resolve() == self.destination.resolve():
                self.mutate(self.source)
            return result
        with patch.object(p, 'atomic_new', side_effect=changed), self.assertRaises(SaveError):
            p.save_as(self.document, {'gems': 321}, self.destination)
        self.assertEqual(self.destination.read_bytes(), self.expected)
        self.assertNotEqual(self.source.read_bytes(), self.document.raw)
        backups = [path for path in self.snapshots() if path.suffix.lower() == '.bin']
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), self.document.raw)

    def test_foreign_destination_before_native_readback_is_preserved_and_rejected(self):
        atomic = p.atomic_new
        replacement = []
        def changed(raw, destination):
            result = atomic(raw, destination)
            if Path(destination).resolve() == self.destination.resolve():
                replacement.append(self.mutate(self.destination))
            return result
        with patch.object(p, 'atomic_new', side_effect=changed), self.assertRaises(SaveError):
            p.save_as(self.document, {'gems': 321}, self.destination)
        self.assertEqual(self.destination.read_bytes(), replacement[0])
        self.assertEqual(self.source.read_bytes(), self.document.raw)

    def test_source_or_destination_change_after_native_readback_is_rejected(self):
        for target in ('source', 'destination'):
            with self.subTest(target=target):
                self.source.write_bytes(self.document.raw)
                if self.destination.exists():
                    self.destination.unlink()
                read = p.read_save
                replacement = []
                def changed(path, *args, **kwargs):
                    result = read(path, *args, **kwargs)
                    if Path(path).resolve() == self.destination.resolve():
                        replacement.append(self.mutate(self.source if target == 'source' else self.destination))
                    return result
                with patch.object(p, 'read_save', side_effect=changed), self.assertRaises(SaveError):
                    p.save_as(self.document, {'gems': 321}, self.destination)
                self.assertEqual(len(replacement), 1)
                self.assertEqual((self.source if target == 'source' else self.destination).read_bytes(), replacement[0])
                self.assertTrue(self.destination.is_file())

    def test_success_reads_actual_destination_preserves_inputs_and_restores_backup(self):
        with patch.object(p, 'read_save', wraps=p.read_save) as reader:
            output = p.save_as(self.document, {'gems': 321}, self.destination)
        self.assertEqual(reader.call_count, 1)
        self.assertEqual(Path(reader.call_args.args[0]).resolve(), self.destination.resolve())
        self.assertEqual(output.raw, self.expected)
        self.assertEqual(output.source.resolve(), self.destination.resolve())
        self.assertEqual(self.source.read_bytes(), self.document.raw)
        backup = next(path for path in self.snapshots() if path.suffix.lower() == '.bin')
        self.assertEqual(backup.read_bytes(), self.document.raw)
        restored = p.restore(backup, self.folder / 'restored.bin')
        self.assertEqual(restored.read_bytes(), self.document.raw)
        with self.assertRaises(FileExistsError):
            p.save_as(self.document, {'gems': 123}, self.destination)
        self.assertEqual(self.destination.read_bytes(), self.expected)
