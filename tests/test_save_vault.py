"""Procedural native copies exercise private vault integrity and copy-only safety."""
from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.deception4_ps3 import parser
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import save_vault as vault
from tests.test_ps3_new_families import fixture
from tests.test_ps3_expansion import PS3ContextTests


class SaveVaultTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.raw = fixture(parser)
        self.source = self.folder / 'copies' / 'DATA.BIN'
        self.source.parent.mkdir()
        self.source.write_bytes(self.raw)
        self.metadata = self.source.parent / 'PARAM.SFO'
        self.context = PS3ContextTests.metadata('NPUB31442-GAMEDATA-10') + b'original opaque private tail'
        self.metadata.write_bytes(self.context)
        self.store = vault.SaveVault.create(self.folder / 'vault')

    def snapshot(self, **kwargs):
        return self.store.snapshot(parser.GAME_ID, self.source, **kwargs)

    def test_native_roundtrip_preserves_complete_original_companion_and_reopen_history(self):
        record = self.snapshot(label='Before battle')
        self.assertEqual(record.filename, self.source.name)
        self.assertEqual(record.size_bytes, len(self.raw) + len(self.context))
        self.assertTrue(self.store.verify(record.id)[0].valid)
        restored = self.store.restore(record.id, self.folder / 'restored')
        self.assertEqual(restored.read_bytes(), self.raw)
        self.assertEqual((restored.parent / 'PARAM.SFO').read_bytes(), self.context)
        self.assertEqual(parser.read_save(restored).raw, self.raw)
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertEqual(self.metadata.read_bytes(), self.context)
        reopened = vault.SaveVault(self.store.root)
        self.assertEqual(reopened.list_snapshots(), (record,))
        # Records and reports never retain source paths, payload or owner objects.
        self.assertNotIn(str(self.source.parent), json.dumps(asdict(record)))
        self.assertNotIn('opaque private tail', json.dumps(asdict(record)))

    def test_explicit_profile_missing_companion_and_corruption_never_capture(self):
        for game_id in ('not-a-game', 'dw6_ps3'):
            with self.assertRaises(SaveError):
                self.store.snapshot(game_id, self.source)
        self.metadata.unlink()
        with self.assertRaises(SaveError):
            self.snapshot()
        self.metadata.write_bytes(self.context)
        self.source.write_bytes(self.raw[:-1])
        with self.assertRaises(SaveError):
            self.snapshot()
        self.assertEqual(self.store.list_snapshots(), ())

    def test_snapshot_branch_ancestry_relabel_compare_and_leaf_delete(self):
        first = self.snapshot()
        self.store.branch('experiment', first.id)
        self.source.write_bytes(parser.serialize(parser.read_save(self.source), {'warl': 42}))
        second = self.snapshot(branch='experiment', label='Changed')
        self.assertEqual(second.parent_id, first.id)
        self.assertEqual(self.store.list_snapshots(branch='experiment'), (first, second))
        self.assertEqual(self.store.list_snapshots(branch='main'), (first,))
        self.assertEqual(self.store.list_branches(), {'main': first.id, 'experiment': second.id})
        comparison = self.store.compare(first.id, second.id)
        self.assertTrue(comparison.same_profile)
        self.assertFalse(comparison.identical_gameplay_bytes)
        self.assertTrue(comparison.identical_context_bytes)
        self.assertEqual(comparison.changed_field_ids, ('warl',))
        self.assertGreater(comparison.changed_byte_count, 0)
        updated = self.store.relabel(second.id, 'Reviewed')
        self.assertEqual(updated.label, 'Reviewed')
        self.assertEqual(self.store.verify(second.id)[0].valid, True)
        with self.assertRaises(SaveError):
            self.store.delete(first.id)
        self.store.delete(second.id)
        self.assertEqual(self.store.list_snapshots(), (first,))
        self.assertEqual(self.store.list_branches()['experiment'], first.id)
        # Removing an index reference does not erase privately retained backups.
        self.assertTrue((self.store.objects / second.id / second.filename).is_file())
        with self.assertRaises(SaveError):
            self.store.restore(second.id, self.folder / 'deleted')

    def test_context_comparison_separates_same_gameplay_from_different_native_slot(self):
        first = self.snapshot()
        self.metadata.write_bytes(PS3ContextTests.metadata('NPUB31442-GAMEDATA-11'))
        second = self.snapshot()
        result = self.store.compare(first.id, second.id)
        self.assertTrue(result.identical_gameplay_bytes)
        self.assertFalse(result.identical_context_bytes)
        self.assertEqual(result.changed_files, ('PARAM.SFO',))
        self.assertEqual(result.changed_field_ids, ())

    def test_new_destination_only_and_live_cloud_paths_are_blocked(self):
        record = self.snapshot()
        for existing in (self.source.parent, self.source, self.store.root):
            with self.assertRaises((SaveError, FileExistsError)):
                self.store.restore(record.id, existing)
        with self.assertRaises(SaveError):
            self.store.restore(record.id, self.store.root / 'new-copy')
        live = self.folder / 'Steam' / 'userdata' / '123' / '456' / 'remote'
        live.mkdir(parents=True)
        for operation in (lambda: self.store.restore(record.id, live / 'copy'),
                          lambda: vault.SaveVault.create(live / 'vault')):
            with self.assertRaises(SaveError):
                operation()
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_snapshot_and_original_companion_tamper_blocks_verify_restore_and_compare(self):
        for filename in ('DATA.BIN', 'PARAM.SFO'):
            with self.subTest(filename=filename):
                record = self.snapshot()
                path = self.store.objects / record.id / filename
                raw = path.read_bytes()
                path.write_bytes(raw[:-1] + bytes((raw[-1] ^ 1,)))
                self.assertFalse(self.store.verify(record.id)[0].valid)
                destination = self.folder / ('restore-' + filename)
                with self.assertRaises(SaveError):
                    self.store.restore(record.id, destination)
                self.assertFalse(destination.exists())
                with self.assertRaises(SaveError):
                    self.store.compare(record.id, record.id)

    def test_mutation_after_second_native_read_cannot_verify_or_compare(self):
        for operation_name in ('verify', 'compare'):
            with self.subTest(operation=operation_name):
                record = self.snapshot()
                target = self.store.objects / record.id / record.filename
                original = parser.read_save
                calls = 0
                def changing(*args, **kwargs):
                    nonlocal calls
                    document = original(*args, **kwargs)
                    calls += 1
                    if calls == 2:
                        target.write_bytes(self.raw[:-1])
                    return document
                with patch.object(parser, 'read_save', side_effect=changing):
                    if operation_name == 'verify':
                        self.assertFalse(self.store.verify(record.id)[0].valid)
                    else:
                        with self.assertRaises(SaveError):
                            self.store.compare(record.id, record.id)

    def test_unindexed_context_injection_is_detected(self):
        record = self.snapshot()
        (self.store.objects / record.id / 'extra-private-context').write_bytes(b'injected')
        self.assertFalse(self.store.verify(record.id)[0].valid)

    def test_index_checksum_schema_paths_cycles_and_bounds_reject_tamper(self):
        first = self.snapshot()
        path = self.store.root / 'index.json'
        original = path.read_bytes()
        path.write_bytes(original[:-1])
        with self.assertRaises(SaveError):
            self.store.list_snapshots()
        for mutate in (lambda p: p['snapshots'][0].update(filename='../DATA.BIN'),
                       lambda p: p['snapshots'][0]['files'][0].update(relative_path='../secret'),
                       lambda p: p['snapshots'][0]['files'][0].update(relative_path='x\\y'),
                       lambda p: p['snapshots'][0]['files'][0].update(size_bytes=True),
                       lambda p: p['snapshots'][0].update(parent_id=first.id),
                       lambda p: p['branches'].update(main='f' * 32),
                       lambda p: p['snapshots'][0].update(label='x' * 201),
                       lambda p: p.update(schema_version=True)):
            envelope = json.loads(original)
            mutate(envelope['payload'])
            envelope['sha256'] = vault._digest(vault._json(envelope['payload']))
            path.write_bytes(vault._json(envelope))
            with self.assertRaises(SaveError):
                vault.SaveVault(self.store.root)
        path.write_bytes(original)
        self.assertTrue(self.store.verify(first.id)[0].valid)

    def test_aliases_reject_source_companion_storage_index_and_destination(self):
        record = self.snapshot()
        for kind in ('symlink', 'hardlink'):
            with self.subTest(kind=kind):
                alias = self.source.with_name('ALIAS.BIN')
                try:
                    if kind == 'symlink':
                        alias.symlink_to(self.source)
                    else:
                        os.link(self.source, alias)
                except OSError:
                    if kind == 'symlink':
                        continue
                    raise
                with self.assertRaises(SaveError):
                    self.store.snapshot(parser.GAME_ID, alias)
                alias.unlink()
                context_alias = self.metadata.with_name('context-alias')
                if kind == 'symlink':
                    self.metadata.rename(context_alias)
                    self.metadata.symlink_to(context_alias)
                else:
                    os.link(self.metadata, context_alias)
                with self.assertRaises(SaveError):
                    self.snapshot()
                if kind == 'symlink':
                    self.metadata.unlink()
                    context_alias.rename(self.metadata)
                else:
                    context_alias.unlink()
        alias_dir = self.folder / 'linked-parent'
        try:
            alias_dir.symlink_to(self.source.parent, target_is_directory=True)
        except OSError:
            return
        with self.assertRaises(SaveError):
            self.store.snapshot(parser.GAME_ID, alias_dir / self.source.name)
        with self.assertRaises(SaveError):
            self.store.restore(record.id, alias_dir / 'restore')
        object_path = self.store.objects / record.id / record.filename
        copy = object_path.with_name('saved-external')
        object_path.rename(copy)
        object_path.symlink_to(copy)
        self.assertFalse(self.store.verify(record.id)[0].valid)
        object_path.unlink()
        copy.rename(object_path)
        index = self.store.root / 'index.json'
        external = self.folder / 'index-backup'
        index.rename(external)
        index.symlink_to(external)
        with self.assertRaises(SaveError):
            self.store.list_snapshots()

    def test_changed_source_and_still_valid_context_during_qualification_are_rejected(self):
        original = parser.read_save
        calls = 0
        def changing(*args, **kwargs):
            nonlocal calls
            document = original(*args, **kwargs)
            calls += 1
            if calls == 1:
                self.metadata.write_bytes(PS3ContextTests.metadata('NPUB31442-GAMEDATA-11'))
            return document
        with patch.object(parser, 'read_save', side_effect=changing):
            with self.assertRaisesRegex(SaveError, 'context changed'):
                self.snapshot()
        self.assertEqual(self.store.list_snapshots(), ())
        self.metadata.write_bytes(self.context)
        def changing_raw(*args, **kwargs):
            document = original(*args, **kwargs)
            self.source.write_bytes(self.raw[:-1])
            return document
        with patch.object(parser, 'read_save', side_effect=changing_raw):
            with self.assertRaises(SaveError):
                self.snapshot()

    def test_file_context_metadata_and_storage_limits_are_enforced(self):
        with patch.object(vault, 'MAX_FILE_BYTES', len(self.raw) - 1):
            with self.assertRaises(SaveError):
                self.snapshot()
        with patch.object(vault, 'MAX_CONTEXT_BYTES', len(self.context) - 1):
            with self.assertRaises(SaveError):
                self.snapshot()
        with patch.object(vault, 'MAX_BUNDLE_BYTES', len(self.raw)):
            with self.assertRaises(SaveError):
                self.snapshot()
        with patch.object(vault, 'MAX_STORAGE_BYTES', len(self.raw)):
            with self.assertRaises(SaveError):
                self.snapshot()
        self.snapshot()
        with patch.object(vault, 'MAX_SNAPSHOTS', 1):
            with self.assertRaises(SaveError):
                self.snapshot()
        with patch.object(vault, 'MAX_INDEX_BYTES', 10):
            with self.assertRaises(SaveError):
                self.store.list_snapshots()

    def test_busy_cross_instance_lock_blocks_conflicting_operations_and_releases_on_failure(self):
        reopened = vault.SaveVault(self.store.root)
        with self.store._locked():
            for operation in (reopened.list_snapshots, lambda: reopened.snapshot(parser.GAME_ID, self.source)):
                with self.assertRaisesRegex(SaveError, 'busy'):
                    operation()
        with patch.object(self.store, '_save', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.snapshot()
        self.assertFalse((self.store.root / '.lock').exists())
        self.assertEqual(reopened.list_snapshots(), ())
        # Failure leaves unindexed immutable files; a later snapshot is independent.
        record = self.snapshot()
        self.assertTrue(self.store.verify(record.id)[0].valid)

    def test_index_changed_during_commit_is_not_overwritten(self):
        first = self.snapshot()
        index = self.store.root / 'index.json'
        original = vault._new
        replacement = b'externally replaced index'
        def replacing(raw, path, **kwargs):
            result = original(raw, path, **kwargs)
            if Path(path).name.startswith('.index-'):
                index.write_bytes(replacement)
            return result
        with patch.object(vault, '_new', side_effect=replacing):
            with self.assertRaisesRegex(SaveError, 'index changed'):
                self.store.relabel(first.id, 'Conflict')
        self.assertEqual(index.read_bytes(), replacement)

    def test_portable_branch_label_identifier_and_snapshot_source_constraints(self):
        record = self.snapshot()
        for branch in ('../escape', '', 'x' * 65, 'bad/name', 'bad.'):
            with self.assertRaises(SaveError):
                self.snapshot(branch=branch)
        with self.assertRaises(SaveError):
            self.store.relabel(record.id, 'x\nprivate')
        for operation in (lambda: self.store.restore('../escape', self.folder / 'invalid'),
                          lambda: self.store.branch('main', record.id),
                          lambda: self.store.list_snapshots(branch='missing'),
                          lambda: self.store.snapshot(parser.GAME_ID, self.store.objects / record.id / record.filename)):
            with self.assertRaises(SaveError):
                operation()

    def test_nonportable_save_name_cannot_poison_existing_vault(self):
        record = self.snapshot()
        for name in ('CON.bin', 'trailing.bin.', 'bad:name.bin'):
            renamed = self.source.with_name(name)
            self.source.rename(renamed)
            try:
                # The selected extension gate or portable-name gate rejects it.
                with self.assertRaises(SaveError):
                    self.store.snapshot(parser.GAME_ID, renamed)
                self.assertEqual(self.store.list_snapshots(), (record,))
            finally:
                renamed.rename(self.source)

    def test_directory_replacement_with_identical_file_inodes_is_rejected(self):
        original = self.store._materialize
        moved = self.folder / 'old-copies'
        def replacing(bundle, directory):
            original(bundle, directory)
            self.source.parent.rename(moved)
            self.source.parent.mkdir()
            for item in moved.iterdir():
                item.rename(self.source.parent / item.name)
        with patch.object(self.store, '_materialize', side_effect=replacing):
            with self.assertRaisesRegex(SaveError, 'source changed|directory changed identity'):
                self.snapshot()
        self.assertEqual(self.store.list_snapshots(), ())

    def test_restored_and_stored_files_are_requalified_without_profile_fallback(self):
        record = self.snapshot()
        with patch.object(parser, 'read_save', side_effect=SaveError('native rejection')):
            self.assertFalse(self.store.verify(record.id)[0].valid)
            with self.assertRaises(SaveError):
                self.store.restore(record.id, self.folder / 'rejected')
        self.assertFalse((self.folder / 'rejected').exists())

    def test_native_emulator_live_policy_blocks_restore_before_any_write(self):
        from koei_editor.games.nobunaga_ambition_nes import parser as nes
        from tests.test_nobunaga_ambition_nes import procedural_raw
        source = self.folder / 'battery-copy.sav'
        source.write_bytes(procedural_raw())
        record = self.store.snapshot(nes.GAME_ID, source, branch='nes')
        live = self.folder / 'emulator-live'
        live.mkdir()
        (live / 'nobunaga.nes').write_bytes(b'nonexecuted installation marker')
        destination = live / 'restore'
        with self.assertRaisesRegex(SaveError, 'live emulator'):
            self.store.restore(record.id, destination)
        self.assertFalse(destination.exists())
        self.assertTrue(self.store.verify(record.id)[0].valid)

    def test_dw3_bespoke_tagged_document_roundtrip_remains_byte_exact(self):
        from tests.test_elixirs_v11 import synthetic_reset_save
        from koei_editor.games.dw3.save_parser import read_save
        source = self.folder / 'copied-dw3.sav'
        raw = synthetic_reset_save().encrypted
        source.write_bytes(raw)
        record = self.store.snapshot('dw3', source, branch='dw3')
        restored = self.store.restore(record.id, self.folder / 'dw3-restored')
        self.assertEqual(restored.read_bytes(), raw)
        self.assertEqual(read_save(restored).encrypted, raw)
        self.assertTrue(self.store.verify(record.id)[0].valid)

    def test_vita_nested_original_context_preserved(self):
        from koei_editor.games.aot1_vita import parser as vita
        from tests.test_aot1_vita import fixture as vita_fixture
        directory = self.folder / 'vita'
        directory.mkdir()
        source = directory / 'app0000.dat'
        source.write_bytes(vita_fixture())
        (directory / 'sce_sys').mkdir()
        original = vita.identity_metadata('/PCSB00898') + b'private-original-tail'
        (directory / 'sce_sys' / 'param.sfo').write_bytes(original)
        record = self.store.snapshot(vita.GAME_ID, source, branch='vita')
        restored = self.store.restore(record.id, self.folder / 'vita-restored')
        self.assertEqual(restored.read_bytes(), source.read_bytes())
        self.assertEqual((restored.parent / 'sce_sys/param.sfo').read_bytes(), original)
        self.assertTrue(self.store.verify(record.id)[0].valid)

    def test_steam_owner_bound_native_context_preserved_without_synthesis(self):
        from koei_editor.games.samurai5_pc import parser as steam
        from koei_editor.shared.steam_owner import read_owner
        from tests.test_samurai5_pc import procedural, sidecar
        directory = self.folder / 'steam-copy'
        directory.mkdir()
        source = directory / 'input-copy.bin'
        metadata = sidecar(directory)
        source.write_bytes(procedural(read_owner(source)))
        record = self.store.snapshot(steam.GAME_ID, source, branch='steam')
        restored = self.store.restore(record.id, self.folder / 'steam-restored')
        self.assertEqual(restored.read_bytes(), source.read_bytes())
        self.assertEqual((restored.parent / metadata.name).read_bytes(), metadata.read_bytes())
        self.assertTrue(self.store.verify(record.id)[0].valid)


if __name__ == '__main__':
    unittest.main()
