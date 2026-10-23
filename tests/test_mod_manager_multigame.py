"""Documented install policies; all game/loader/assets are procedural fixtures."""
import dataclasses
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from koei_editor.shared.mod_manager import (
    InstallationError, ModManager, PackageError, ProfileError, SafetyError,
    get_mod_adapter, review_archive, supported_mod_games,
)


def nioh3_root(path):
    path.mkdir()
    (path / 'Nioh3.exe').write_bytes(b'procedural game marker; never executed')
    (path / 'DINPUT8.dll').write_bytes(b'procedural loader marker; never executed')
    (path / 'plugins').mkdir()
    (path / 'plugins/LooseFileLoader.dll').write_bytes(b'procedural plugin marker; never executed')
    return path


def package(path, mod_id='example-mod', files=None, game_id='nioh3_pc'):
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('koei-mod.json', json.dumps(dict(schema_version=1, game_id=game_id,
                    id=mod_id, name=mod_id, version='1.0', dependencies=[], conflicts=[])))
        for name, data in (files or {'Wrapper/0xA1B2C3D4.g1t': b'procedural texture'}).items():
            z.writestr(name, data)
    return path


class MultiGameModManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.area = Path(self.temp.name).resolve()
        self.game = nioh3_root(self.area / 'game')
        self.manager = ModManager(self.area / 'state', self.game, game_id='nioh3_pc')

    def imported(self, mod_id='example-mod', files=None):
        return self.manager.import_archive(package(self.area / (mod_id + '.zip'), mod_id, files))

    def test_catalog_has_explicit_distinct_methods_and_no_in_game_claim(self):
        adapters = supported_mod_games()
        self.assertEqual([item.game_id for item in adapters], ['nioh2_pc', 'nioh3_pc'])
        self.assertEqual({item.disable_policy for item in adapters}, {'folder_suffix', 'remove'})
        self.assertTrue(all(item.platform == 'PC' and not item.in_game_verified and item.evidence for item in adapters))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            adapters[0].game_id = 'another-game'
        with self.assertRaises(InstallationError):
            ModManager(self.area / 'unknown-state', game_id='dw8xl')
        self.assertFalse((self.area / 'unknown-state').exists())

    def test_read_only_review_matches_real_import_without_creating_manager_state(self):
        archive = package(self.area / 'review.zip')
        before = {p: p.read_bytes() for p in self.area.rglob('*') if p.is_file()}
        review = review_archive(archive, game_id='nioh3_pc')
        self.assertEqual({p: p.read_bytes() for p in self.area.rglob('*') if p.is_file()}, before)
        self.assertEqual(review.game_id, 'nioh3_pc')
        self.assertEqual(review.files[0].path, '0xA1B2C3D4.g1t')
        imported = self.manager.import_archive(archive)
        self.assertEqual(review.files, imported.files)
        self.assertEqual(review.content_sha256, imported.content_sha256)
        self.assertEqual(review.id, imported.id)
        json.dumps(dataclasses.asdict(review))

    def test_wrong_game_manifest_and_unsupported_payload_fail_both_review_and_import(self):
        for index, files in enumerate([
            {'first/0x12345678.g1t': b'a', 'second/0x87654321.g1t': b'b'},
            {'too/deep/0x12345678.g1t': b'a'}, {'mods/model.g1m': b'a'},
            {'mod.ini': b'[mod]'}, {'0x123456789.g1t': b'a'},
            {'../0x12345678.g1t': b'a'}, {'DINPUT8.dll': b'loader'},
            {'0x12345678.g1t': b'a', '12345678.G1M': b'b'},
        ]):
            archive = package(self.area / f'invalid-{index}.zip', files=files)
            for method in (lambda: review_archive(archive, game_id='nioh3_pc'),
                           lambda: self.manager.import_archive(archive)):
                with self.subTest(files=tuple(files)), self.assertRaises(PackageError):
                    method()
        archive = package(self.area / 'foreign.zip', game_id='nioh2_pc')
        with self.assertRaises(PackageError):
            self.manager.import_archive(archive)
        self.assertEqual(self.manager.mods(), ())

    def test_flat_payloads_accept_all_three_documented_extensions(self):
        mod = self.imported(files={'12345678.G1M': b'model', '0x11111111.g1t': b'texture', '0x22222222.g1ts': b'stream'})
        self.assertEqual(len(mod.files), 3)

    def test_wrong_game_marker_and_missing_linked_empty_or_oversized_loader_block_changes(self):
        wrong = self.area / 'wrong-game'; wrong.mkdir()
        (wrong / 'nioh2.exe').write_bytes(b'procedural wrong game marker')
        with self.assertRaises(InstallationError):
            self.manager.set_game_root(wrong)
        mod = self.imported()
        self.manager.set_profile_mod_enabled('default', mod.id, True)
        loader = self.game / 'plugins/LooseFileLoader.dll'; original = loader.read_bytes()
        for data in [None, b'']:
            if loader.exists(): loader.unlink()
            if data is not None: loader.write_bytes(data)
            with self.assertRaises(InstallationError):
                self.manager.apply_profile('default', loader_confirmed=True)
            self.assertFalse((self.game / 'mods').exists())
        loader.write_bytes(original)
        with loader.open('wb') as stream:
            stream.truncate(128 * 1024 * 1024 + 1)
        with self.assertRaises(InstallationError):
            self.manager.apply_profile('default', loader_confirmed=True)
        self.assertFalse((self.game / 'mods').exists())

    def test_apply_disable_reenable_uses_owned_removal_not_nioh2_suffix(self):
        originals = {p: p.read_bytes() for p in self.game.rglob('*') if p.is_file()}
        mod = self.imported()
        self.manager.set_profile_mod_enabled('default', mod.id, True)
        self.manager.apply_profile('default', loader_confirmed=True)
        target = self.game / 'mods' / mod.id
        self.assertTrue((target / '0xA1B2C3D4.g1t').is_file())
        inactive = self.manager.create_profile('Inactive')
        self.manager.apply_profile(inactive.id, loader_confirmed=True)
        self.assertFalse(target.exists())
        self.assertFalse((self.game / 'mods' / (mod.id + ' DISABLED')).exists())
        self.assertEqual(self.manager.installation['installed'], {})
        self.assertEqual(self.manager.mods()[0].content_sha256, mod.content_sha256)
        self.manager.apply_profile('default', loader_confirmed=True)
        self.assertEqual((target / '0xA1B2C3D4.g1t').read_bytes(), b'procedural texture')
        self.assertEqual({p: p.read_bytes() for p in originals}, originals)
        reopened = ModManager(self.area / 'state', self.game, game_id='nioh3_pc')
        self.assertTrue(reopened.mods()[0].installed)

    def test_no_undocumented_inactive_install_is_performed(self):
        mod = self.imported()
        with self.assertRaisesRegex(ProfileError, 'Apply Profile'):
            self.manager.install_mod(mod.id, loader_confirmed=True)
        self.assertFalse((self.game / 'mods').exists())

    def test_cross_profile_resource_hash_aliases_are_conflicts_even_with_identical_bytes(self):
        first = self.imported('first-mod', {'12345678.g1m': b'identical'})
        second = self.imported('second-mod', {'0x12345678.g1t': b'identical'})
        self.manager.set_profile_mod_enabled('default', first.id, True)
        with self.assertRaisesRegex(ProfileError, 'conflict'):
            self.manager.set_profile_mod_enabled('default', second.id, True)
        self.assertEqual(self.manager.profiles()[0].enabled_mods, (first.id,))
        self.assertFalse((self.game / 'mods').exists())

    def test_unmanaged_hash_alias_in_root_or_first_level_blocks_overlay_and_remains_untouched(self):
        mod = self.imported(files={'12345678.g1t': b'new'})
        self.manager.set_profile_mod_enabled('default', mod.id, True)
        mods = self.game / 'mods'; mods.mkdir()
        for folder in [mods, mods / 'UserMod']:
            folder.mkdir(exist_ok=True)
            external = folder / '0X12345678.g1m'; external.write_bytes(b'unmanaged')
            with self.assertRaises(ProfileError):
                self.manager.apply_profile('default', loader_confirmed=True)
            self.assertEqual(external.read_bytes(), b'unmanaged')
            self.assertFalse((mods / mod.id).exists())
            external.unlink()

    def test_changed_owned_mod_refuses_disable_and_keeps_profile_journal_safe(self):
        mod = self.imported()
        self.manager.set_profile_mod_enabled('default', mod.id, True)
        self.manager.apply_profile('default', loader_confirmed=True)
        target = self.game / 'mods' / mod.id / '0xA1B2C3D4.g1t'; target.write_bytes(b'foreign modification')
        inactive = self.manager.create_profile('Inactive')
        with self.assertRaises(SafetyError):
            self.manager.apply_profile(inactive.id, loader_confirmed=True)
        self.assertEqual(target.read_bytes(), b'foreign modification')
        self.assertFalse(self.manager.has_pending_transaction)

    def test_state_libraries_and_same_mod_ids_are_isolated_without_migrating_nioh2(self):
        other = ModManager(self.area / 'state')
        from tests.test_mod_manager import make_archive
        other.import_archive(make_archive(self.area / 'nioh2.zip', mod_id='example-mod'))
        nioh3 = self.imported()
        self.assertNotEqual(other.mods()[0].content_sha256, nioh3.content_sha256)
        self.assertEqual(other.state_dir, self.area / 'state')
        self.assertEqual(self.manager.state_dir, self.area / 'state/games/nioh3_pc')
        self.assertEqual(ModManager(self.area / 'state').mods(), other.mods())

    def test_postcommit_cleanup_interruption_recovers_removal_without_losing_library(self):
        mod = self.imported(); self.manager.set_profile_mod_enabled('default', mod.id, True)
        self.manager.apply_profile('default', loader_confirmed=True)
        inactive = self.manager.create_profile('Inactive')
        with patch.object(self.manager, '_finish_committed_transaction', side_effect=OSError('procedural crash')):
            with self.assertRaises(OSError):
                self.manager.apply_profile(inactive.id, loader_confirmed=True)
        self.assertTrue(self.manager.has_pending_transaction)
        reopened = ModManager(self.area / 'state', self.game, game_id='nioh3_pc')
        self.assertFalse(reopened.has_pending_transaction)
        self.assertFalse((self.game / 'mods' / mod.id).exists())
        self.assertEqual(reopened.mods()[0].content_sha256, mod.content_sha256)
        self.assertFalse(list(self.game.glob('.ktmm-remove-*')))

    def test_failed_external_conflict_inspection_restores_profile_intent_and_disk(self):
        mod = self.imported()
        before = (self.manager.install_state_dir / 'state.json').read_bytes()
        with patch.object(self.manager, '_external_resource_issues', side_effect=SafetyError('external area changed')):
            with self.assertRaises(SafetyError):
                self.manager.set_profile_mod_enabled('default', mod.id, True)
        self.assertEqual(self.manager.profiles()[0].enabled_mods, ())
        self.assertEqual((self.manager.install_state_dir / 'state.json').read_bytes(), before)
