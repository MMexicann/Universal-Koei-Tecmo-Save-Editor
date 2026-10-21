"""PS4 copied backups bind original context and retain concurrently replaced files."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw8xl import ps4_export as p
from tests.test_conversion import write_copy


class PS4CopyRaceTests(unittest.TestCase):
    def test_backup_readbacks_every_created_file_without_deleting_foreign_replacements(self):
        for target in ('raw', 'manifest', 'companion', 'context'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                source = write_copy(Path(temporary) / 'source', p.GAME_ID)
                document = p.read_save(source)
                atomic = p.atomic_new
                observed = {}
                foreign = b'Another application replaced a completed backup file.'
                def replace_after_context(data, destination):
                    result = atomic(data, destination)
                    if result.name.endswith('.context.json'):
                        raw = result.with_name(result.name.removesuffix('.context.json'))
                        observed.update(raw=raw, manifest=raw.with_suffix('.json'),
                                        companion=raw.with_name(raw.name + '.param.sfo'), context=result)
                        observed[target].write_bytes(foreign)
                    return result
                with patch.object(p, 'atomic_new', side_effect=replace_after_context), self.assertRaises(SaveError):
                    p.backup(document)
                self.assertEqual(observed[target].read_bytes(), foreign)
                self.assertTrue(all(path.is_file() for path in observed.values()))
                self.assertEqual(source.read_bytes(), document.raw)

    def test_backup_rejects_oversized_and_mismatched_snapshot_manifests(self):
        for mutation in ('oversized', 'game', 'kind', 'size', 'hash'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                source = write_copy(Path(temporary) / 'source', p.GAME_ID)
                document = p.read_save(source)
                original = p.snapshot_backup
                observed = {}
                def replace_manifest(*args, **kwargs):
                    result = original(*args, **kwargs)
                    path = result.with_suffix('.json')
                    manifest = json.loads(path.read_bytes())
                    if mutation == 'oversized':
                        raw = b' ' * 4097
                    else:
                        key, value = {'game': ('game_id', 'dw8xl_vita'), 'kind': ('kind', 'other'),
                                      'size': ('size_bytes', p.SAVE_SIZE - 1), 'hash': ('sha256', '0' * 64)}[mutation]
                        manifest[key] = value
                        raw = json.dumps(manifest).encode()
                    path.write_bytes(raw)
                    observed.update(path=path, raw=raw)
                    return result
                with patch.object(p, 'snapshot_backup', side_effect=replace_manifest), self.assertRaises(SaveError):
                    p.backup(document)
                self.assertEqual(observed['path'].read_bytes(), observed['raw'])
                self.assertEqual(source.read_bytes(), document.raw)

    def test_restore_rejects_swapped_valid_same_title_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = write_copy(Path(temporary) / 'source', p.GAME_ID)
            document = p.read_save(source)
            backup = p.backup(document)
            alternate = p.context_raw(source) + b'\0'
            # Both companions independently pass title/structure validation.
            p.title_id(alternate, p.TITLE_ID)
            backup.with_name(backup.name + '.param.sfo').write_bytes(alternate)
            source.parent.joinpath('sce_sys', 'param.sfo').write_bytes(alternate)
            destination = source.with_name('restored.bin')
            with self.assertRaises(SaveError):
                p.restore(backup, destination)
            self.assertFalse(destination.exists())

    def test_restore_context_is_bounded_closed_and_bound_to_gameplay(self):
        for mutation in ('oversized', 'invalid_json', 'missing', 'wrong_game', 'wrong_kind',
                         'extra_key', 'context_digest', 'save_digest', 'short_digest', 'wrong_type'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                source = write_copy(Path(temporary) / 'source', p.GAME_ID)
                document = p.read_save(source)
                backup = p.backup(document)
                path = backup.with_name(backup.name + '.context.json')
                context = json.loads(path.read_bytes())
                if mutation == 'missing':
                    path.unlink()
                elif mutation in ('oversized', 'invalid_json'):
                    path.write_bytes(b' ' * 1025 if mutation == 'oversized' else b'{')
                else:
                    key, value = {'wrong_game': ('game_id', 'dw8xl_vita'),
                                  'wrong_kind': ('kind', 'other'), 'extra_key': ('extra', 1),
                                  'context_digest': ('context_sha256', '0' * 64),
                                  'save_digest': ('save_sha256', '0' * 64),
                                  'short_digest': ('context_sha256', 'ab'),
                                  'wrong_type': ('context_sha256', [])}[mutation]
                    context[key] = value
                    path.write_text(json.dumps(context))
                destination = source.with_name('restored.bin')
                with self.assertRaises(SaveError):
                    p.restore(backup, destination)
                self.assertFalse(destination.exists())

    def test_restore_keeps_a_validated_snapshot_when_backup_changes_after_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = write_copy(Path(temporary) / 'source', p.GAME_ID)
            document = p.read_save(source)
            backup = p.backup(document)
            destination = source.with_name('restored.bin')
            atomic = p.restore_snapshot.__globals__['atomic_new']
            def replace_before_write(raw, output):
                backup.write_bytes(b'foreign replacement after validated read')
                return atomic(raw, output)
            with patch('koei_editor.shared.copy_storage.atomic_new', side_effect=replace_before_write):
                result = p.restore(backup, destination)
            self.assertEqual(result.read_bytes(), document.raw)
            self.assertEqual(backup.read_bytes(), b'foreign replacement after validated read')

    def test_restore_detects_destination_context_change_after_actual_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = write_copy(Path(temporary) / 'source', p.GAME_ID)
            document = p.read_save(source)
            backup = p.backup(document)
            destination = source.with_name('restored.bin')
            atomic = p.restore_snapshot.__globals__['atomic_new']
            def replace_after_write(raw, output):
                result = atomic(raw, output)
                source.parent.joinpath('sce_sys', 'param.sfo').write_bytes(p.context_raw(source) + b'\0')
                return result
            with patch('koei_editor.shared.copy_storage.atomic_new', side_effect=replace_after_write), self.assertRaises(SaveError):
                p.restore(backup, destination)
            self.assertEqual(destination.read_bytes(), document.raw)
            self.assertEqual(source.read_bytes(), document.raw)
