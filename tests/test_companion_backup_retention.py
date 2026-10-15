"""A failed companion backup must never erase a completed or replaced file.

These use procedural inputs through the actual game readers and backup paths.
They exercise storage failure behavior, not native-save or game-load evidence.
"""
from contextlib import contextmanager
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError


# All existing companion-backed backup implementations with this failure path.
PROFILES = (
    'bladestorm_ps3', 'gundam1_ps3', 'gundam3_ps3', 'gundam_reborn_ps3',
    'trinity_ps3', 'pw1_ps3', 'pw2_ps3', 'pw3_ps3', 'aot1_vita',
    'meruru_plus_vita', 'berserk_vita', 'doa5_ps3', 'dw8_ps3', 'dw8xl_ps3',
    'dw8xl_ps4', 'p5strikers_ps4', 'sophie2_ps4', 'samurai5_pc', 'abyss_pc',
    'ninja_gaiden_black_xbox', 'totori_ps3', 'meruru_ps3', 'rorona_ps3',
)


@contextmanager
def opened_profile(game_id):
    """Open distinctive existing procedural fixtures with their exact context."""
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary).resolve()
        if game_id == 'dw8xl_ps4':
            from koei_editor.games.dw8xl import ps4_export as backend
            from tests.test_conversion import write_copy
            source = write_copy(folder / 'copies', game_id)
        elif game_id in ('totori_ps3', 'meruru_ps3', 'rorona_ps3'):
            from koei_editor.games.arland_ps3 import backend as hooks
            from tests.test_arland_ps3 import copied
            backend = importlib.import_module(f'koei_editor.games.{game_id}.parser')
            source = copied(folder, backend)
        else:
            backend = importlib.import_module(f'koei_editor.games.{game_id}.parser')
            if game_id in ('pw1_ps3', 'pw2_ps3'):
                from tests.test_pirate_warriors_ps3 import fixture, sfo
                source = folder / 'DATA.BIN'
                source.write_bytes(fixture(backend))
                (folder / 'PARAM.SFO').write_bytes(sfo(backend.TITLE_IDS[0] + '-00'))
            elif game_id == 'samurai5_pc':
                from koei_editor.shared.steam_owner import read_owner
                from tests.test_samurai5_pc import procedural, sidecar
                sidecar(folder)
                source = folder / 'copy.bin'
                source.write_bytes(procedural(read_owner(source)))
            elif game_id in ('abyss_pc', 'ninja_gaiden_black_xbox'):
                fixture_module = importlib.import_module(f'tests.test_{game_id}')
                source = fixture_module.procedural(folder)
            elif game_id == 'sophie2_ps4':
                from tests.test_sophie2_ps4 import source as make_source
                source = make_source(folder)
            else:
                fixture_module = importlib.import_module(f'tests.test_{game_id}')
                extension = ('' if game_id == 'meruru_plus_vita' else
                             '.dat' if game_id in ('aot1_vita', 'berserk_vita', 'doa5_ps3', 'trinity_ps3')
                             else '.bin')
                source = folder / ('copy' + extension)
                generator = (fixture_module.procedural_raw if game_id == 'dw8_ps3'
                             else fixture_module.fixture)
                source.write_bytes(generator())
                if game_id in ('meruru_plus_vita', 'berserk_vita', 'doa5_ps3'):
                    fixture_module.write_context(folder)
                elif game_id == 'p5strikers_ps4':
                    fixture_module.add_context(folder)
                elif game_id in ('dw8_ps3', 'dw8xl_ps3'):
                    fixture_module.context(folder)
                elif game_id == 'gundam1_ps3':
                    (folder / 'PARAM.SFO').write_bytes(fixture_module.metadata())
                elif game_id == 'aot1_vita':
                    (folder / 'sce_sys').mkdir()
                    (folder / 'sce_sys/param.sfo').write_bytes(backend.identity_metadata('/PCSB00898'))
                else:
                    identity = {
                        'bladestorm_ps3': 'BLES00113PLAY0',
                        'gundam3_ps3': 'BLUS30703-00',
                        'gundam_reborn_ps3': 'NPEB02060-00',
                        'trinity_ps3': 'BLUS30503-PLAY02',
                        'pw3_ps3': 'NPEB02211-00',
                    }[game_id]
                    (folder / 'PARAM.SFO').write_bytes(backend.identity_metadata(identity))
        if game_id not in ('totori_ps3', 'meruru_ps3', 'rorona_ps3'):
            hooks = backend
        document = backend.read_save(source)
        yield backend, hooks, document


def companion_path(backup, game_id):
    if game_id == 'gundam1_ps3':
        return backup.with_suffix('.sfo')
    suffix = '.param.sfo' if game_id == 'dw8xl_ps4' else '.context.json'
    return backup.with_name(backup.name + suffix)


class CompanionBackupRetentionTests(unittest.TestCase):
    def test_failed_companion_write_retains_snapshot_and_manifest_but_cannot_restore(self):
        for game_id in PROFILES:
            with self.subTest(game_id=game_id), opened_profile(game_id) as (backend, hooks, document):
                snapshots = []
                original_snapshot = hooks.snapshot_backup

                def capture_snapshot(*args, **kwargs):
                    result = original_snapshot(*args, **kwargs)
                    snapshots.append(result)
                    return result

                with patch.object(hooks, 'snapshot_backup', side_effect=capture_snapshot), \
                        patch.object(hooks, 'atomic_new', side_effect=OSError('companion disk failure')):
                    with self.assertRaisesRegex(OSError, 'companion disk failure'):
                        backend.backup(document)
                self.assertEqual(len(snapshots), 1)
                backup = snapshots[0]
                self.assertEqual(backup.read_bytes(), document.raw)
                manifest = json.loads(backup.with_suffix('.json').read_bytes())
                self.assertEqual(manifest['sha256'], document.sha256)
                self.assertFalse(companion_path(backup, game_id).exists())
                # DW8 XL PS4 is conversion-only and has no standalone restore.
                if game_id != 'dw8xl_ps4':
                    destination = document.source.with_name('restored' + document.source.suffix)
                    with self.assertRaises((SaveError, OSError)):
                        backend.restore(backup, destination)
                    self.assertFalse(destination.exists())
                self.assertEqual(document.source.read_bytes(), document.raw)

    def test_failed_backup_preserves_concurrent_replacements_of_every_completed_path(self):
        for game_id in PROFILES:
            with self.subTest(game_id=game_id), opened_profile(game_id) as (backend, hooks, document):
                captured = []
                original_snapshot = hooks.snapshot_backup
                foreign = b'Another application owns these replacement bytes.'

                def replace_after_snapshot(*args, **kwargs):
                    result = original_snapshot(*args, **kwargs)
                    captured.append(result)
                    result.write_bytes(foreign)
                    result.with_suffix('.json').write_bytes(foreign)
                    companion_path(result, game_id).write_bytes(foreign)
                    return result

                with patch.object(hooks, 'snapshot_backup', side_effect=replace_after_snapshot), \
                        patch.object(hooks, 'atomic_new', side_effect=FileExistsError('occupied companion')):
                    with self.assertRaisesRegex(FileExistsError, 'occupied companion'):
                        backend.backup(document)
                backup = captured[0]
                for path in (backup, backup.with_suffix('.json'), companion_path(backup, game_id)):
                    self.assertEqual(path.read_bytes(), foreign)
                self.assertEqual(document.source.read_bytes(), document.raw)

    def test_post_companion_source_failure_keeps_original_backup_and_completed_companion(self):
        # These profiles additionally recheck the source after companion creation.
        for game_id in ('gundam1_ps3', 'dw8xl_ps4', 'samurai5_pc', 'abyss_pc',
                        'ninja_gaiden_black_xbox'):
            with self.subTest(game_id=game_id), opened_profile(game_id) as (backend, hooks, document):
                created = []
                original_atomic = hooks.atomic_new

                def mutate_after_companion(raw, destination):
                    result = original_atomic(raw, destination)
                    created.append((Path(destination), raw))
                    document.source.write_bytes(b'Concurrent source update')
                    return result

                with patch.object(hooks, 'atomic_new', side_effect=mutate_after_companion):
                    with self.assertRaises(SaveError):
                        backend.backup(document)
                self.assertEqual(len(created), 1)
                companion, expected = created[0]
                self.assertEqual(companion.read_bytes(), expected)
                backups = list((document.source.parent / 'UniversalEditorBackups').glob('*' + document.source.suffix))
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].read_bytes(), document.raw)
                self.assertEqual(json.loads(backups[0].with_suffix('.json').read_bytes())['sha256'], document.sha256)
                self.assertEqual(document.source.read_bytes(), b'Concurrent source update')

    def test_failed_abyss_private_context_copy_preserves_a_concurrent_replacement(self):
        with opened_profile('abyss_pc') as (backend, _hooks, document):
            directory = document.source.parent / 'private-copy'
            foreign = b'Concurrent companion replacement'
            original_check = backend.require_matching_owner

            def replace_context(owner, source):
                if Path(source).parent != directory:
                    return original_check(owner, source)
                (directory / document.owner.basename).write_bytes(foreign)
                raise SaveError('The copied owner context changed.')

            with patch.object(backend, 'require_matching_owner', side_effect=replace_context):
                with self.assertRaisesRegex(SaveError, 'copied owner context changed'):
                    backend.prepare_copy_context(document, directory)
            self.assertEqual((directory / document.owner.basename).read_bytes(), foreign)
            self.assertEqual(document.source.read_bytes(), document.raw)


class TaggedBackupRetentionTests(unittest.TestCase):
    def setUp(self):
        from koei_editor.games.dw3 import save_writer
        from koei_editor.games.dw3.save_parser import read_save
        from tests.test_elixirs_v11 import synthetic_reset_save
        self.backend = save_writer
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name).resolve()
        self.source = self.folder / 'source.sav'
        self.source.write_bytes(synthetic_reset_save().encrypted)
        self.document = read_save(self.source)

    def test_manifest_disk_failure_preserves_completed_dw3_snapshot(self):
        original_atomic = self.backend._atomic_write

        def fail_manifest(raw, destination, *args, **kwargs):
            if Path(destination).suffix == '.json':
                raise OSError('Manifest disk failure')
            return original_atomic(raw, destination, *args, **kwargs)

        folder = self.folder / 'backups'
        with patch.object(self.backend, '_atomic_write', side_effect=fail_manifest):
            with self.assertRaisesRegex(OSError, 'Manifest disk failure'):
                self.backend.backup_save(self.document, folder)
        backups = list(folder.glob('*.sav'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), self.document.encrypted)
        self.assertFalse(backups[0].with_suffix('.json').exists())
        destination = self.folder / 'restore.sav'
        with self.assertRaises(OSError):
            self.backend.restore_backup(backups[0], destination)
        self.assertFalse(destination.exists())
        self.assertEqual(self.source.read_bytes(), self.document.encrypted)

    def test_manifest_collision_preserves_concurrent_dw3_replacements(self):
        original_atomic = self.backend._atomic_write
        captured = []
        foreign = b'Concurrent replacement of a DW3 backup'

        def collide(raw, destination, *args, **kwargs):
            destination = Path(destination)
            if destination.suffix == '.json':
                captured[0].write_bytes(foreign)
                destination.write_bytes(foreign)
                raise FileExistsError('Concurrent manifest creation')
            result = original_atomic(raw, destination, *args, **kwargs)
            captured.append(result)
            return result

        with patch.object(self.backend, '_atomic_write', side_effect=collide):
            with self.assertRaisesRegex(FileExistsError, 'Concurrent manifest creation'):
                self.backend.backup_save(self.document, self.folder / 'backups')
        self.assertEqual(captured[0].read_bytes(), foreign)
        self.assertEqual(captured[0].with_suffix('.json').read_bytes(), foreign)
        self.assertEqual(self.source.read_bytes(), self.document.encrypted)
