"""Backup failures must preserve files concurrently replaced by another app."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw6_ps3 import japanese_export as japanese
from koei_editor.shared import copy_storage, ps3_copy
from tests.test_conversion import write_copy


class CopyBackupRaceTests(unittest.TestCase):
    def test_ps3_backup_checks_all_created_files_even_when_source_stays_unchanged(self):
        for target in ('raw', 'manifest', 'context'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                source = write_copy(Path(temporary) / 'copy', 'dw6_ps3_jp')
                document = japanese.read_save(source)
                atomic = ps3_copy.atomic_new
                observed = {}
                foreign = b'Another application replaced this completed backup.'

                def replace_after_context(data, destination):
                    result = atomic(data, destination)
                    raw_path = result.with_name(result.name.removesuffix('.context.json'))
                    paths = {'raw': raw_path, 'manifest': raw_path.with_suffix('.json'),
                             'context': result}
                    paths[target].write_bytes(foreign)
                    observed.update(paths)
                    return result

                with patch.object(ps3_copy, 'atomic_new', side_effect=replace_after_context):
                    with self.assertRaises(SaveError):
                        japanese.backup(document)
                self.assertEqual(observed[target].read_bytes(), foreign)
                self.assertEqual(source.read_bytes(), document.raw)
                self.assertTrue(all(path.is_file() for path in observed.values()))

    def test_ps3_backup_rejects_oversized_and_mismatched_manifest_metadata(self):
        for mutation in ('oversized', 'wrong game', 'wrong kind', 'wrong size', 'wrong hash'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                source = write_copy(Path(temporary) / 'copy', 'dw6_ps3_jp')
                document = japanese.read_save(source)
                original = ps3_copy.snapshot_backup
                observed = {}

                def change_manifest(*args, **kwargs):
                    result = original(*args, **kwargs)
                    path = result.with_suffix('.json')
                    manifest = json.loads(path.read_bytes())
                    if mutation == 'oversized':
                        replacement = b' ' * 4097
                    else:
                        key, value = {'wrong game': ('game_id', 'dw6_ps3'),
                                      'wrong kind': ('kind', 'other'),
                                      'wrong size': ('size_bytes', len(document.raw) - 1),
                                      'wrong hash': ('sha256', '0' * 64)}[mutation]
                        manifest[key] = value
                        replacement = json.dumps(manifest).encode('utf-8')
                    path.write_bytes(replacement)
                    observed.update(path=path, raw=replacement)
                    return result

                with patch.object(ps3_copy, 'snapshot_backup', side_effect=change_manifest):
                    with self.assertRaises(SaveError):
                        japanese.backup(document)
                self.assertEqual(observed['path'].read_bytes(), observed['raw'])
                self.assertEqual(source.read_bytes(), document.raw)

    def test_manifest_collision_preserves_external_raw_and_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'source.dat'
            source.write_bytes(b'original opened snapshot')
            atomic = copy_storage.atomic_new
            observed = {}

            def collide(data, destination):
                destination = Path(destination)
                if destination.suffix == '.json':
                    observed['raw'].write_bytes(b'external raw replacement')
                    destination.write_bytes(b'external manifest')
                    observed['manifest'] = destination
                    raise FileExistsError('A racing manifest exists.')
                result = atomic(data, destination)
                observed['raw'] = result
                return result

            with patch.object(copy_storage, 'atomic_new', side_effect=collide), self.assertRaises(FileExistsError):
                copy_storage.snapshot_backup(source.read_bytes(), source, 'dw6')
            self.assertEqual(observed['raw'].read_bytes(), b'external raw replacement')
            self.assertEqual(observed['manifest'].read_bytes(), b'external manifest')
            self.assertEqual(source.read_bytes(), b'original opened snapshot')

    def test_context_collision_preserves_foreign_metadata_and_completed_backup(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = write_copy(Path(temporary) / 'copy', 'dw6_ps3_jp')
            document = japanese.read_save(source)
            observed = []

            def collide(data, destination):
                destination = Path(destination)
                destination.write_bytes(b'external context replacement')
                observed.append(destination)
                raise FileExistsError('A racing context exists.')

            with patch.object(ps3_copy, 'atomic_new', side_effect=collide), self.assertRaises(FileExistsError):
                japanese.backup(document)
            self.assertEqual(observed[0].read_bytes(), b'external context replacement')
            snapshots = list((source.parent / 'UniversalEditorBackups').glob('*.BIN'))
            self.assertEqual(len(snapshots), 1)
            self.assertEqual(snapshots[0].read_bytes(), document.raw)
            self.assertTrue(snapshots[0].with_suffix('.json').is_file())

    def test_late_ps3_source_check_preserves_replaced_backup_and_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = write_copy(Path(temporary) / 'copy', 'dw6_ps3_jp')
            document = japanese.read_save(source)
            atomic = ps3_copy.atomic_new
            observed = {}

            def replace_after_context(data, destination):
                result = atomic(data, destination)
                raw_path = result.with_name(result.name.removesuffix('.context.json'))
                manifest = raw_path.with_suffix('.json')
                raw_path.write_bytes(b'external changed backup')
                manifest.write_bytes(b'external changed manifest')
                source.write_bytes(document.raw[:-1])
                observed.update(raw=raw_path, manifest=manifest)
                return result

            with patch.object(ps3_copy, 'atomic_new', side_effect=replace_after_context), self.assertRaises(SaveError):
                japanese.backup(document)
            self.assertEqual(observed['raw'].read_bytes(), b'external changed backup')
            self.assertEqual(observed['manifest'].read_bytes(), b'external changed manifest')


if __name__ == '__main__':
    unittest.main()
