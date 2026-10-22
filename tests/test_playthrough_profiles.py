"""Integration coverage for safe, vault-backed playthrough environments."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.deception4_ps3 import parser
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import playthrough_profiles as playthrough_profiles_module
from koei_editor.shared.save_vault import SaveVault
from koei_editor.shared.playthrough_profiles import (
    PlaythroughProfileStore,
    PlaythroughPreparationError,
    ProfileComponentSnapshot,
)
from tests import test_ps3_expansion
from tests.test_ps3_new_families import fixture


class PlaythroughProfileIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source_dir = self.root / 'copied-save'
        self.source_dir.mkdir()
        self.source = self.source_dir / 'DATA.BIN'
        self.raw = fixture(parser)
        self.context = (test_ps3_expansion.PS3ContextTests.metadata('NPUB31442-GAMEDATA-10') +
                        b'private original context')
        self.source.write_bytes(self.raw)
        (self.source_dir / 'PARAM.SFO').write_bytes(self.context)
        self.vault = SaveVault.create(self.root / 'vault')
        self.snapshot = self.vault.snapshot(parser.GAME_ID, self.source,
                                            label='Profile base')
        self.store = PlaythroughProfileStore(self.vault)

    @staticmethod
    def components(game_version='1.02'):
        return (
            ProfileComponentSnapshot(
                'mod_configuration', 'mod_manager', 1, parser.GAME_ID,
                game_version, {'enabled_mods': ['cosmetic-one'], 'load_order': [0]}),
            ProfileComponentSnapshot(
                'game_settings', 'configuration_manager', 1, parser.GAME_ID,
                game_version, {'resolution': '1920x1080', 'windowed': True}),
            ProfileComponentSnapshot(
                'character_build', 'character_workshop', 1, parser.GAME_ID,
                game_version, {'character': 'test-officer', 'skills': ['guard']}),
        )

    def make_profile(self, *, components=None, version='1.02'):
        return self.store.create_profile(
            'Story run', parser.GAME_ID, version, self.snapshot.id,
            components=self.components(version) if components is None else components)

    def copy(self, destination, raw=None, context=None):
        destination.mkdir(parents=True)
        save = destination / 'DATA.BIN'
        save.write_bytes(self.raw if raw is None else raw)
        (destination / 'PARAM.SFO').write_bytes(self.context if context is None else context)
        return save

    def test_profile_persists_exact_game_and_version_compatibility(self):
        profile = self.make_profile()

        reopened = PlaythroughProfileStore(self.vault)
        self.assertEqual(reopened.load(profile.id), profile)
        self.assertEqual(reopened.list_profiles(game_id=parser.GAME_ID), (profile,))
        preview = reopened.preview(profile.id, '1.02')
        self.assertTrue(preview.compatible)
        self.assertEqual(preview.report['installed_game_version_source'], 'user_asserted')
        self.assertFalse(preview.report['components_applied'])
        self.assertFalse(preview.report['live_save_written'])
        mismatch = reopened.preview(profile.id, '1.03')
        self.assertFalse(mismatch.compatible)
        self.assertEqual(mismatch.report['report_scope'], 'compatibility_preview')
        self.assertTrue(self.vault.verify(self.snapshot.id)[0].valid)

    def test_all_component_kinds_are_digest_bound_and_staged_as_inert_json(self):
        profile = self.make_profile()
        destination = self.root / 'prepared'

        result = self.store.prepare_environment(profile.id, destination, '1.02')

        component_files = {
            'mod_configuration': destination / 'components' / 'mod_configuration.json',
            'game_settings': destination / 'components' / 'game_settings.json',
            'character_build': destination / 'components' / 'character_build.json',
        }
        self.assertEqual(set(component_files), {item.component for item in profile.components})
        for component in profile.components:
            with self.subTest(component=component.component):
                artifact_path = component_files[component.component]
                self.assertTrue(artifact_path.is_file())
                artifact = json.loads(artifact_path.read_text(encoding='utf-8'))
                self.assertEqual(artifact['payload'], component.payload)
                contract = {key: artifact[key] for key in (
                    'component', 'provider', 'schema_version', 'game_id',
                    'game_version', 'payload')}
                encoded = json.dumps(contract, sort_keys=True,
                                     separators=(',', ':'), ensure_ascii=True).encode('ascii')
                self.assertEqual(hashlib.sha256(encoded).hexdigest(), artifact['sha256'])
                self.assertNotIn('executable', artifact)

        self.assertEqual(result.save_path.read_bytes(), self.raw)
        self.assertEqual((result.save_path.parent / 'PARAM.SFO').read_bytes(), self.context)
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertEqual((self.source.parent / 'PARAM.SFO').read_bytes(), self.context)
        report = json.loads(result.report_path.read_text(encoding='utf-8'))
        self.assertEqual(report, result.report)
        self.assertFalse(report['live_save_written'])
        self.assertEqual(report['installed_game_version_source'], 'user_asserted')
        self.assertEqual(report['profile_id'], profile.id)

    def test_switch_backup_captures_only_an_independent_copy_and_restores_new_directory(self):
        profile = self.make_profile()
        current_dir = self.root / 'current-copy'
        active_bytes = parser.serialize(parser.read_save(self.source), {'warl': 42})
        active_context = self.context + b' independent copy'
        active_save = self.copy(current_dir, raw=active_bytes, context=active_context)
        current_bytes = active_save.read_bytes()
        current_context = (current_dir / 'PARAM.SFO').read_bytes()
        destination = self.root / 'playthrough-environment'

        result = self.store.prepare_environment(
            profile.id, destination, '1.02', active_save_copy=active_save)

        self.assertTrue(result.backup_snapshot_id)
        self.assertTrue(self.vault.verify(result.backup_snapshot_id)[0].valid)
        self.assertEqual(active_save.read_bytes(), current_bytes)
        self.assertEqual((current_dir / 'PARAM.SFO').read_bytes(), current_context)
        self.assertEqual(result.save_path.read_bytes(), self.raw)
        self.assertNotEqual(result.save_path.parent, current_dir)
        self.assertTrue(destination.is_dir())
        backup_copy = self.root / 'verified-active-backup'
        backup_save = self.vault.restore(result.backup_snapshot_id, backup_copy)
        self.assertEqual(backup_save.read_bytes(), current_bytes)
        self.assertEqual((backup_copy / 'PARAM.SFO').read_bytes(), current_context)

    def test_preview_and_prepare_reject_a_missing_or_corrupt_snapshot(self):
        profile = self.make_profile(components=())
        stored = self.vault.objects / self.snapshot.id / self.snapshot.filename
        stored.write_bytes(self.raw[:-1])

        preview = self.store.preview(profile.id, '1.02')
        self.assertFalse(preview.compatible)
        self.assertTrue(preview.blockers)
        destination = self.root / 'must-not-exist'
        with self.assertRaises((SaveError, OSError, ValueError)):
            self.store.prepare_environment(profile.id, destination, '1.02')
        self.assertFalse(destination.exists())

    def test_profile_creation_rejects_cross_game_snapshot_or_component_versions(self):
        with self.assertRaises((SaveError, ValueError)):
            self.store.create_profile('Wrong game', 'not-a-game', '1.02', self.snapshot.id)
        with self.assertRaises((SaveError, ValueError)):
            self.make_profile(components=self.components(game_version='1.03'))

    def test_restore_never_targets_existing_vault_or_live_destinations(self):
        profile = self.make_profile(components=())
        existing = self.root / 'existing'
        existing.mkdir()
        sentinel = existing / 'keep.txt'
        sentinel.write_text('preserve', encoding='utf-8')
        with self.assertRaises((FileExistsError, SaveError)):
            self.store.prepare_environment(profile.id, existing, '1.02')
        self.assertEqual(sentinel.read_text(encoding='utf-8'), 'preserve')

        with self.assertRaises(SaveError):
            self.store.prepare_environment(profile.id, self.vault.root / 'inside-vault', '1.02')
        self.assertFalse((self.vault.root / 'inside-vault').exists())

        live = self.root / 'Steam' / 'userdata' / '123456' / '527270' / 'remote'
        live.mkdir(parents=True)
        save = live / 'DATA.BIN'
        save.write_bytes(self.raw)
        before = save.read_bytes()
        with self.assertRaises(SaveError):
            self.store.prepare_environment(profile.id, live / 'profile-switch', '1.02')
        self.assertEqual(save.read_bytes(), before)

    def test_live_save_cannot_be_used_as_automatic_pre_switch_backup(self):
        profile = self.make_profile(components=())
        live = self.root / 'Steam' / 'userdata' / '123456' / '527270' / 'remote'
        live.mkdir(parents=True)
        live_save = live / 'DATA.BIN'
        live_save.write_bytes(self.raw)
        (live / 'PARAM.SFO').write_bytes(self.context)
        before = {item.name: item.read_bytes() for item in live.iterdir() if item.is_file()}

        with self.assertRaises(SaveError):
            self.store.prepare_environment(
                profile.id, self.root / 'isolated', '1.02', active_save_copy=live_save)

        self.assertEqual(before, {item.name: item.read_bytes() for item in live.iterdir() if item.is_file()})
        self.assertEqual(self.vault.list_snapshots(), (self.snapshot,))
        self.assertFalse((self.root / 'isolated').exists())

    def test_restore_failure_surfaces_completed_pre_switch_backup(self):
        profile = self.make_profile(components=())
        current_dir = self.root / 'current-copy'
        active_save = self.copy(current_dir)
        destination = self.root / 'partial-environment'

        def fail_restore(_snapshot_id, _destination):
            raise SaveError('injected restore failure')

        self.vault.restore = fail_restore
        with self.assertRaises(PlaythroughPreparationError) as caught:
            self.store.prepare_environment(
                profile.id, destination, '1.02', active_save_copy=active_save)

        backup_id = caught.exception.backup_snapshot_id
        self.assertIn(backup_id, str(caught.exception))
        self.assertTrue(self.vault.verify(backup_id)[0].valid)
        self.assertTrue(destination.is_dir())
        self.assertEqual(active_save.read_bytes(), self.raw)

    def test_tampered_profile_metadata_is_rejected_before_environment_creation(self):
        profile = self.make_profile(components=())
        # Each profile is an immutable manifest; mutate persisted metadata to
        # verify that a changed profile cannot be silently accepted.
        profile_file = (self.vault.root / 'playthrough_profiles' /
                        (profile.id + '.json'))
        original = profile_file.read_bytes()
        data = json.loads(original)
        data['payload']['game_version'] = '1.03'
        profile_file.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises((SaveError, ValueError)):
            self.store.load(profile.id)
        destination = self.root / 'tampered-profile-output'
        with self.assertRaises((SaveError, ValueError)):
            self.store.prepare_environment(profile.id, destination, '1.02')
        self.assertFalse(destination.exists())

    def test_tampered_component_payload_is_rejected_even_with_valid_profile_envelope(self):
        profile = self.make_profile()
        profile_file = (self.vault.root / 'playthrough_profiles' /
                        (profile.id + '.json'))
        data = json.loads(profile_file.read_text(encoding='utf-8'))
        payload = data['payload']
        payload['components'][0]['payload']['enabled_mods'][0] = 'changed-after-export'
        canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'),
                               ensure_ascii=True).encode('ascii')
        data['sha256'] = hashlib.sha256(canonical).hexdigest()
        profile_file.write_text(json.dumps(data), encoding='utf-8')

        with self.assertRaises((SaveError, ValueError)):
            self.store.load(profile.id)
        destination = self.root / 'tampered-component-output'
        with self.assertRaises((SaveError, ValueError)):
            self.store.prepare_environment(profile.id, destination, '1.02')
        self.assertFalse(destination.exists())
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertEqual((self.source.parent / 'PARAM.SFO').read_bytes(), self.context)

    def test_components_parent_symlink_race_cannot_redirect_staging_outside_environment(self):
        profile = self.make_profile()
        destination = self.root / 'race-environment'
        component_parent = destination / 'components'
        outside = self.root / 'outside-components'
        outside.mkdir()
        original_ordinary = playthrough_profiles_module._ordinary
        race_injected = False

        def replace_parent_after_preflight(path, **kwargs):
            nonlocal race_injected
            checked = original_ordinary(path, **kwargs)
            if (not race_injected and Path(path) == component_parent
                    and kwargs.get('directory') is True):
                # This hook runs after the service's parent preflight and
                # before the first staged component is written.
                component_parent.rmdir()
                try:
                    component_parent.symlink_to(outside, target_is_directory=True)
                except OSError as error:
                    self.skipTest(f'Host cannot create a directory symlink: {error}')
                race_injected = True
            return checked

        with patch.object(playthrough_profiles_module, '_ordinary',
                          side_effect=replace_parent_after_preflight):
            with self.assertRaises(PlaythroughPreparationError) as caught:
                self.store.prepare_environment(profile.id, destination, '1.02')

            self.assertEqual(caught.exception.destination.resolve(), destination.resolve())
        self.assertTrue(race_injected, 'the test must inject the race after parent preflight')
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse((outside / 'mod_configuration.json').exists())
        self.assertFalse((outside / 'playthrough-report.json').exists())

    def test_environment_destination_symlink_race_cannot_redirect_report_outside(self):
        profile = self.make_profile(components=())
        destination = self.root / 'report-race-environment'
        displaced_destination = self.root / 'displaced-report-race-environment'
        outside = self.root / 'outside-report'
        outside.mkdir()
        original_new_child_bound = playthrough_profiles_module.new_child_bound
        race_injected = False

        def replace_destination_before_report(data, directory, name, expected_identity):
            nonlocal race_injected
            if (not race_injected and Path(directory) == destination
                    and name == 'playthrough-report.json'):
                # Save restoration and the destination identity capture have
                # completed; swap the root just before the report is created.
                destination.rename(displaced_destination)
                try:
                    destination.symlink_to(outside, target_is_directory=True)
                except OSError as error:
                    self.skipTest(f'Host cannot create a directory symlink: {error}')
                race_injected = True
            return original_new_child_bound(data, directory, name, expected_identity)

        with patch.object(playthrough_profiles_module, 'new_child_bound',
                          side_effect=replace_destination_before_report):
            with self.assertRaises(PlaythroughPreparationError) as caught:
                self.store.prepare_environment(profile.id, destination, '1.02')

            self.assertEqual(caught.exception.destination.resolve(), destination.resolve())
        self.assertTrue(race_injected, 'the test must inject the race before report creation')
        self.assertTrue(displaced_destination.is_dir())
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
