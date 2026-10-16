"""Procedural copy-only vault history, context, corruption and race checks."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import save_vault as vault_module
from tests.test_verified_editors import synthetic_raw


class SaveVaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name).resolve()
        self.source = self.folder / 'source.dat'
        self.source.write_bytes(synthetic_raw('dw8xl'))
        self.vault = vault_module.Vault(self.folder / 'vault')

    def capture(self, label='First', **kwargs):
        return self.vault.import_copy('dw8xl', self.source, label, **kwargs)

    def test_import_search_collections_branches_and_parent_history(self):
        self.vault.create_collection('Campaign')
        first = self.capture('Chapter one', collection='Campaign')
        left = self.capture('Challenge route', collection='Campaign', branch='challenge', parent_id=first['id'])
        right = self.capture('Story route', collection='Campaign', branch='story', parent_id=first['id'])
        self.assertEqual([row['id'] for row in self.vault.history(left['id'])], [left['id'], first['id']])
        self.assertEqual([row['id'] for row in self.vault.history(right['id'])], [right['id'], first['id']])
        self.assertEqual(self.vault.snapshots(query='CHALLENGE route', branch='challenge')[0]['id'], left['id'])
        self.assertEqual(self.vault.snapshots(game_id='pw3'), ())
        self.assertEqual(self.vault.collections(), ('Campaign',))
        first['context']['foreign'] = 'bad'
        self.assertEqual(self.vault.snapshots()[-1]['context'], {})
        self.assertEqual(self.source.read_bytes(), synthetic_raw('dw8xl'))
        with self.assertRaises(SaveError):
            self.capture(parent_id=left['id'], collection='Different')

    def test_same_content_has_one_immutable_blob_but_distinct_versions(self):
        first = self.capture()
        second = self.capture('Second', parent_id=first['id'])
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(first['blob'], second['blob'])
        self.assertEqual(len(list((self.vault.root / 'blobs').iterdir())), 1)
        self.assertEqual(self.vault.verify(first['id']).raw, self.source.read_bytes())

    def test_comparison_uses_native_fields_and_never_applies_changes(self):
        first = self.capture()
        adapter = get_game('dw8xl').get_scalar_adapter()
        doc = adapter.read_save(self.source)
        self.source.write_bytes(adapter.serialize(doc, {'gold': 12345}))
        second = self.capture('Edited copy', parent_id=first['id'])
        comparison = self.vault.compare(first['id'], second['id'])
        self.assertEqual([(row.id, row.left, row.right) for row in comparison.rows], [('gold', 50, 12345)])
        self.assertEqual(self.vault.verify(first['id']).raw, synthetic_raw('dw8xl'))

    def test_restore_exports_new_directory_and_rejects_existing_and_cloud(self):
        row = self.capture()
        path = self.vault.restore(row['id'], self.folder / 'export')
        self.assertEqual(path.read_bytes(), self.source.read_bytes())
        self.assertEqual(get_game('dw8xl').read_save(path).sha256, row['blob'])
        with self.assertRaises(FileExistsError):
            self.vault.export(row['id'], path.parent)
        self.assertEqual(path.read_bytes(), synthetic_raw('dw8xl'))
        with self.assertRaises(SaveError):
            self.vault.export(row['id'], self.folder / 'Steam' / 'userdata' / 'copy')

    def test_blob_corruption_and_working_copy_corruption_are_never_repaired(self):
        row = self.capture()
        blob = self.vault.root / 'blobs' / row['blob']
        blob.write_bytes(b'corrupt')
        with self.assertRaises(SaveError):
            self.vault.verify(row['id'])
        with self.assertRaises(SaveError):
            self.vault.export(row['id'], self.folder / 'damaged-export')
        self.assertEqual(blob.read_bytes(), b'corrupt')

    def test_catalog_hash_chain_catches_older_revision_corruption_and_gaps(self):
        self.capture(); self.capture('Second'); self.capture('Third')
        oldest = self.vault.root / 'catalog' / '00000001.json'
        raw = oldest.read_bytes()
        oldest.write_bytes(raw.replace(b'First', b'Other'))
        with self.assertRaises(SaveError):
            self.vault.snapshots()
        oldest.write_bytes(raw)
        oldest.unlink()
        with self.assertRaises(SaveError):
            self.vault.snapshots()

    def test_malformed_duplicate_keys_traversal_and_oversized_catalog_rejected(self):
        row = self.capture()
        index_path = self.vault.root / 'catalog' / '00000001.json'
        original = index_path.read_bytes()
        index_path.write_bytes(b'{"schema":1,"schema":1}')
        with self.assertRaises(SaveError):
            self.vault.snapshots()
        index = json.loads(original)
        index['snapshots'][0]['filename'] = '../source.dat'
        index_path.write_text(json.dumps(index), encoding='utf-8')
        with self.assertRaises(SaveError):
            self.vault.verify(row['id'])
        index_path.write_bytes(original)
        with patch.object(vault_module, 'MAX_INDEX_BYTES', 10):
            with self.assertRaises(SaveError):
                self.vault.snapshots()

    def test_exclusive_writer_lock_prevents_lost_updates_and_is_not_auto_broken(self):
        with self.vault._writer():
            with self.assertRaises(SaveError):
                vault_module.Vault(self.vault.root).create_collection('Other writer')
        self.assertFalse((self.vault.root / '.writer-lock').exists())
        (self.vault.root / '.writer-lock').mkdir()
        with self.assertRaises(SaveError):
            self.capture()
        self.assertTrue((self.vault.root / '.writer-lock').is_dir())

    def test_late_catalog_failure_retains_completed_copies_and_blobs(self):
        with patch.object(self.vault, '_commit', side_effect=SaveError('Injected catalog race')):
            with self.assertRaises(SaveError):
                self.capture()
        self.assertEqual(self.vault.snapshots(), ())
        copies = list((self.vault.root / 'copies').iterdir())
        self.assertEqual(len(copies), 1)
        self.assertEqual((copies[0] / self.source.name).read_bytes(), self.source.read_bytes())
        self.assertEqual(len(list((self.vault.root / 'blobs').iterdir())), 1)

    def test_catalog_total_bound_rejects_next_revision_without_poisoning_history(self):
        first = self.capture()
        size = (self.vault.root / 'catalog' / '00000001.json').stat().st_size
        with patch.object(vault_module, 'MAX_CATALOG_BYTES', size + 1):
            with self.assertRaises(SaveError):
                self.capture('Would exceed total bound')
            self.assertEqual([row['id'] for row in self.vault.snapshots()], [first['id']])
        self.assertEqual(len(list((self.vault.root / 'catalog').iterdir())), 1)

    def test_source_change_during_context_copy_rejects_import_and_preserves_new_bytes(self):
        backend = get_game('dw8xl').get_scalar_adapter().backend
        def mutate(_document, _destination):
            self.source.write_bytes(b'changed externally')
        with patch.object(backend, 'prepare_copy_context', mutate, create=True):
            with self.assertRaises(SaveError):
                self.capture()
        self.assertEqual(self.source.read_bytes(), b'changed externally')
        self.assertEqual(self.vault.snapshots(), ())

    def test_destination_race_retains_foreign_file_and_fails(self):
        row = self.capture()
        real = vault_module.atomic_new
        destination = self.folder / 'race-output'
        def race(raw, path):
            if Path(path) == destination / self.source.name:
                Path(path).write_bytes(b'foreign completed file')
            return real(raw, path)
        with patch.object(vault_module, 'atomic_new', race):
            with self.assertRaises(FileExistsError):
                self.vault.export(row['id'], destination)
        self.assertEqual((destination / self.source.name).read_bytes(), b'foreign completed file')

    def test_source_hardlinks_and_linked_vault_or_export_ancestor_rejected(self):
        linked = self.folder / 'hardlink.dat'
        try:
            os.link(self.source, linked)
        except OSError as error:
            self.skipTest(str(error))
        with self.assertRaises(SaveError):
            self.capture()
        linked.unlink()
        alias = self.folder / 'alias'
        try:
            alias.symlink_to(self.vault.root, target_is_directory=True)
        except OSError:
            return
        with self.assertRaises(SaveError):
            vault_module.Vault(alias)
        row = self.capture()
        with self.assertRaises(SaveError):
            self.vault.export(row['id'], alias / 'export')

    def test_directory_replacement_is_detected_even_when_original_files_move(self):
        row = self.capture()
        old = self.vault.root / 'blobs'
        moved = self.vault.root / 'old-blobs'
        old.rename(moved); old.mkdir()
        for file in moved.iterdir():
            file.rename(old / file.name)
        with self.assertRaises(SaveError):
            self.vault.verify(row['id'])

    def test_automatic_events_capture_current_copy_not_pending_or_old_backup(self):
        adapter = get_game('dw8xl').get_scalar_adapter()
        original = adapter.read_save(self.source)
        editor = SimpleNamespace(document=original, changes={'gold': 999}, backup=self.folder / 'old-backup')
        first = self.vault.capture_editor_backup('dw8xl', editor, event='opened')
        self.assertEqual(first['label'], 'Opened save copy')
        self.assertEqual(self.vault.verify(first['id']).raw, original.raw)
        self.source.write_bytes(adapter.serialize(original, {'gold': 321}))
        editor.document = adapter.read_save(self.source)
        second = self.vault.capture_editor_backup('dw8xl', editor, event='saved')
        self.assertEqual(second['parent'], first['id'])
        self.assertEqual(second['label'], 'Saved copy')
        self.assertEqual(self.vault.verify(second['id']).raw, self.source.read_bytes())
        self.assertEqual(editor.changes, {'gold': 999})

    def test_source_changed_since_editor_open_is_rejected(self):
        editor = SimpleNamespace(document=get_game('dw8xl').read_save(self.source))
        self.source.write_bytes(b'changed')
        with self.assertRaises(SaveError):
            self.vault.capture_editor_backup('dw8xl', editor)
        self.assertEqual(self.vault.snapshots(), ())


class SaveVaultOpaqueContextTests(unittest.TestCase):
    def test_source_context_hashes_detect_same_size_rewrite_with_restored_mtime(self):
        from koei_editor.games.p5strikers_ps4.context import title_only_sfo
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary).resolve()
            (directory / 'sce_sys').mkdir()
            context = directory / 'sce_sys' / 'param.sfo'
            context.write_bytes(title_only_sfo() + b'opaque original A')
            source = directory / 'APP.BIN'
            initial = vault_module._source_context_hashes(source)
            info = context.stat()
            context.write_bytes(title_only_sfo() + b'opaque original B')
            os.utime(context, ns=(info.st_atime_ns, info.st_mtime_ns))
            self.assertEqual(context.stat().st_size, info.st_size)
            self.assertEqual(context.stat().st_mtime_ns, info.st_mtime_ns)
            self.assertNotEqual(vault_module._source_context_hashes(source), initial)

    def test_self_test_only_context_hook_preserves_full_original_sfo(self):
        from koei_editor.games.p5strikers_ps4.context import title_only_sfo
        from tests.test_p5strikers_ps4 import fixture, add_context
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary).resolve()
            source = folder / 'APP.BIN'; source.write_bytes(fixture())
            opaque = title_only_sfo() + b'opaque untouched original context'
            add_context(folder, opaque)
            vault = vault_module.Vault(folder / 'vault')
            row = vault.import_copy('p5strikers_ps4', source, 'Original PS4 copy')
            result = vault.export(row['id'], folder / 'restored')
            self.assertEqual((result.parent / 'sce_sys' / 'param.sfo').read_bytes(), opaque)
            self.assertEqual(result.read_bytes(), source.read_bytes())

    def test_exact_original_context_is_preserved_and_distinct_automatic_versions_retained(self):
        from koei_editor.games.deception4_ps3 import parser
        from tests.test_ps3_new_families import fixture
        from tests.test_ps3_expansion import PS3ContextTests
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary).resolve()
            source = folder / 'APP.BIN'
            source.write_bytes(fixture(parser))
            context = folder / 'PARAM.SFO'
            original = PS3ContextTests.metadata('NPUB31442-GAMEDATA-10')
            context.write_bytes(original)
            vault = vault_module.Vault(folder / 'vault')
            adapter = get_game(parser.GAME_ID).get_scalar_adapter()
            editor = SimpleNamespace(document=adapter.read_save(source))
            first = vault.capture_editor_backup(parser.GAME_ID, editor)
            # Different valid original private context with identical gameplay.
            context.write_bytes(PS3ContextTests.metadata('NPUB31442-GAMEDATA-11'))
            editor.document = adapter.read_save(source)
            second = vault.capture_editor_backup(parser.GAME_ID, editor)
            self.assertEqual(first['blob'], second['blob'])
            self.assertNotEqual(first['context'], second['context'])
            exported = vault.export(first['id'], folder / 'export')
            self.assertEqual((exported.parent / 'PARAM.SFO').read_bytes(), original)
            self.assertEqual(exported.read_bytes(), source.read_bytes())
            blob = vault.root / 'blobs' / first['context']['PARAM.SFO']
            blob.write_bytes(b'changed opaque context')
            with self.assertRaises(SaveError):
                vault.verify(first['id'])

    def test_valid_companion_replacement_between_expected_read_and_native_qualification_fails(self):
        from koei_editor.games.deception4_ps3 import parser
        from tests.test_ps3_new_families import fixture
        from tests.test_ps3_expansion import PS3ContextTests
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary).resolve()
            source = folder / 'DATA.BIN'; source.write_bytes(fixture(parser))
            (folder / 'PARAM.SFO').write_bytes(PS3ContextTests.metadata('NPUB31442-GAMEDATA-10'))
            vault = vault_module.Vault(folder / 'vault')
            row = vault.import_copy(parser.GAME_ID, source, 'Original')
            stored = vault.root / 'copies' / row['id']
            real = vault_module.save_library._qualify
            def race(adapter, path, *args):
                if Path(path).parent == stored:
                    (stored / 'PARAM.SFO').write_bytes(PS3ContextTests.metadata('NPUB31442-GAMEDATA-11'))
                return real(adapter, path, *args)
            with patch.object(vault_module.save_library, '_qualify', race):
                with self.assertRaises(SaveError):
                    vault.verify(row['id'])
            self.assertEqual((folder / 'PARAM.SFO').read_bytes(), PS3ContextTests.metadata('NPUB31442-GAMEDATA-10'))


if __name__ == '__main__':
    unittest.main()
