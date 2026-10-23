"""App-owned controller profile data never reaches native game or Steam files."""
import json
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from koei_editor.shared import controller_profiles as profiles, copy_storage
from koei_editor.shared.controller_profiles_gui import ControllerProfileWorkspace


class ControllerProfileValidationTests(unittest.TestCase):
    def test_profile_is_bound_to_one_registered_pc_game_and_layout(self):
        value = profiles.create_from_preset('dw8xl', 'keyboard_wasd')
        self.assertEqual(value.game_id, 'dw8xl')
        self.assertEqual(value.layout, 'generic')
        self.assertEqual(value.preset_id, 'keyboard_wasd')
        self.assertEqual(value.bindings[0], profiles.Binding('Move up', 'W'))
        controller = profiles.create_from_preset('dw8xl', 'controller_xbox')
        self.assertEqual(controller.bindings[0], profiles.Binding('Face button 1', controller='A'))
        for game_id in ('not_a_game', 'dw7xl_ps3'):
            with self.subTest(game_id=game_id), self.assertRaises(profiles.ProfileError):
                profiles.create_profile(game_id, 'Personal profile')

    def test_binding_labels_are_bounded_control_free_and_unique(self):
        cases = (
            (profiles.Binding('Attack\nNow', 'A'),),
            (profiles.Binding('Move', 'W'), profiles.Binding('move', 'Up')),
            (profiles.Binding('Attack', 'x' * (profiles.MAX_INPUT + 1)),),
            (profiles.Binding('Empty', '', ''),),
            tuple(profiles.Binding(f'Action {index}', 'A')
                  for index in range(profiles.MAX_BINDINGS + 1)),
        )
        for bindings in cases:
            with self.subTest(bindings=len(bindings)), self.assertRaises(profiles.ProfileError):
                profiles.create_profile('dw8xl', 'Personal profile', bindings=bindings)

    def test_profile_text_rejects_lone_unicode_surrogates(self):
        with self.assertRaises(profiles.ProfileError):
            profiles.create_profile('dw8xl', 'Bad name \ud800')
        with self.assertRaises(profiles.ProfileError):
            profiles.create_profile('dw8xl', 'Valid name',
                                    bindings=(profiles.Binding('Bad action \ud800', 'A'),))

    def test_invalid_profile_id_name_layout_and_preset_are_rejected(self):
        for kwargs in (
            {'profile_id': '../profile'},
            {'name': 'x' * (profiles.MAX_NAME + 1)},
            {'layout': 'unsupported'},
            {'preset_id': '../unknown'},
        ):
            values = {'game_id': 'dw8xl', 'name': 'Valid name'}
            values.update(kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(profiles.ProfileError):
                profiles.create_profile(**values)

    def test_empty_explicit_profile_id_and_preset_name_are_rejected(self):
        with self.assertRaises(profiles.ProfileError):
            profiles.create_profile('dw8xl', 'Valid name', profile_id='')
        with self.assertRaises(profiles.ProfileError):
            profiles.create_from_preset('dw8xl', 'blank', '')

    def test_default_path_is_in_application_configuration_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': directory,
                                         'APPDATA': directory, 'LOCALAPPDATA': directory}):
                path = profiles.default_store_path()
        self.assertEqual(path, Path(directory) / 'UniversalKoeiTecmoSaveEditor' /
                         'controller_profiles.json')
        self.assertNotIn('Steam', str(path))


class ControllerProfileLayoutLocalizationTests(unittest.TestCase):
    def test_german_layout_labels_map_back_to_stable_storage_ids(self):
        workspace = object.__new__(ControllerProfileWorkspace)
        workspace.language = 'de'
        self.assertEqual(workspace._layout_label('generic'), 'Allgemein')
        self.assertEqual(workspace._layout_label('playstation'), 'PlayStation-Beschriftungen')
        self.assertEqual(workspace._layout_id_from_label('Nintendo-Beschriftungen'), 'nintendo')


class ControllerProfileStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = profiles.ProfileStore(self.root / 'config' / 'controller_profiles.json')
        self.profile = profiles.create_from_preset('dw8xl', 'keyboard_wasd', 'My controls')

    def test_new_profile_roundtrip_and_schema_are_bounded(self):
        self.assertEqual(self.store.list_profiles(), ())
        self.store.save_profile(self.profile)
        self.assertEqual(self.store.list_profiles('dw8xl'), (self.profile,))
        data = json.loads(self.store.path.read_bytes())
        self.assertEqual(set(data), {'schema', 'profiles'})
        self.assertEqual(data['schema'], profiles.SCHEMA)
        self.assertEqual(set(data['profiles'][0]),
                         {'profile_id', 'game_id', 'name', 'layout', 'preset_id', 'bindings'})
        self.assertFalse(any(self.root.glob('**/*.tmp')))

    def test_saved_profile_change_creates_previous_store_backup(self):
        first = self.store.save_profile(self.profile)
        updated = profiles.create_profile(first.game_id, first.name, profile_id=first.profile_id,
                                          layout='xbox', preset_id='custom',
                                          bindings=(profiles.Binding('Action', '', 'A'),))
        self.store.save_profile(updated)
        self.assertEqual(self.store.list_profiles(), (updated,))
        self.assertEqual(profiles._decode_store(self.store.backup_path.read_bytes()), (first,))

    def test_backup_and_restore_swap_known_valid_stores_without_losing_current_data(self):
        first = self.profile
        second = profiles.create_from_preset('dw8xl', 'controller_xbox', 'Xbox notes')
        self.store.save_profile(first)
        self.store.save_profile(second)
        self.assertEqual(self.store.list_profiles(), (first, second))
        self.assertEqual(self.store.restore_backup(), (first,))
        self.assertEqual(self.store.list_profiles(), (first,))
        # The replaced store is retained as the next restore point.
        self.assertEqual(profiles._decode_store(self.store.backup_path.read_bytes()), (first, second))
        self.assertEqual(self.store.restore_backup(), (first, second))

    def test_manual_backup_requires_a_valid_existing_store(self):
        self.assertFalse(self.store.create_backup())
        self.store.save_profile(self.profile)
        self.assertTrue(self.store.create_backup())
        self.assertEqual(self.store.backup_path.read_bytes(), self.store.path.read_bytes())

    def test_invalid_or_foreign_store_is_never_silently_overwritten(self):
        invalid = (b'', b'{', b'\xff', b'[]', b'{"schema":true,"profiles":[]}',
                   b'{"schema":1,"schema":1,"profiles":[]}',
                   b'{"schema":1,"profiles":[],"other":1}',
                   b'{"schema":' + b'9' * 5000 + b'}',
                   b' ' * (profiles.MAX_STORE_BYTES + 1),
                   b'[' * 1500 + b']' * 1500)
        for raw in invalid:
            with self.subTest(prefix=raw[:24], size=len(raw)):
                self.store.path.parent.mkdir(parents=True, exist_ok=True)
                self.store.path.write_bytes(raw)
                with self.assertRaises(profiles.ProfileError):
                    self.store.list_profiles()
                with self.assertRaises(profiles.ProfileError):
                    self.store.save_profile(self.profile)
                self.assertEqual(self.store.path.read_bytes(), raw)

    def test_unsupported_profile_data_is_rejected_without_changing_store(self):
        self.store.save_profile(self.profile)
        original = self.store.path.read_bytes()
        invalid = dict(self.profile.__dict__)
        invalid['game_id'] = 'dw7xl_ps3'
        with self.assertRaises(profiles.ProfileError):
            self.store.save_profile(profiles.ControllerProfile(**invalid))
        self.assertEqual(self.store.path.read_bytes(), original)
        self.assertFalse(self.store.delete_profile('dw8xl', '0' * 32))
        with self.assertRaises(profiles.ProfileError):
            self.store.list_profiles('dw7xl_ps3')

    def test_delete_profile_removes_only_exact_game_identity_and_keeps_backup(self):
        self.store.save_profile(self.profile)
        second = profiles.create_from_preset('dw8xl', 'controller_xbox', 'Second profile')
        self.store.save_profile(second)
        self.assertTrue(self.store.delete_profile('dw8xl', self.profile.profile_id))
        self.assertEqual(self.store.list_profiles(), (second,))
        self.assertTrue(self.store.backup_path.exists())

    def test_import_export_roundtrip_and_never_overwrite_existing_export(self):
        destination = self.root / 'portable' / 'controls.ktinput.json'
        self.assertEqual(self.store.export_profile(self.profile, destination), destination)
        self.assertEqual(self.store.import_profile(destination), self.profile)
        original = destination.read_bytes()
        with self.assertRaises(profiles.ProfileError):
            self.store.export_profile(self.profile, destination)
        self.assertEqual(destination.read_bytes(), original)
        imported = self.store.import_profile(destination)
        self.assertEqual(imported, self.profile)
        self.assertEqual(self.store.list_profiles(), ())  # Import reads only; it does not save.

    def test_failed_export_removes_partial_file(self):
        destination = self.root / 'portable' / 'controls.ktinput.json'
        if os.name == 'nt':
            failure = patch.object(copy_storage, '_rename_verified_child_windows',
                                   return_value=-1073741823)
        elif sys.platform.startswith('linux'):
            failure = patch.object(profiles.os, 'fsync', side_effect=OSError('disk full'))
        else:
            with self.assertRaises(profiles.ProfileError):
                self.store.export_profile(self.profile, destination)
            self.assertFalse(destination.exists())
            self.assertFalse(destination.parent.exists())
            return
        with failure:
            with self.assertRaises(profiles.ProfileError):
                self.store.export_profile(self.profile, destination)
        self.assertFalse(destination.exists())
        self.assertEqual(list(destination.parent.iterdir()), [])

    def test_failed_export_preserves_a_concurrent_destination_replacement(self):
        destination = self.root / 'portable' / 'controls.ktinput.json'
        foreign = b'Unrelated concurrent file must survive.'

        def replace_destination_and_fail(_descriptor):
            if destination.exists():
                destination.replace(destination.with_suffix('.displaced'))
            destination.write_bytes(foreign)
            raise OSError('Injected storage failure after concurrent replacement')

        if os.name == 'nt':
            def collide_at_publication(*args):
                destination.write_bytes(foreign)
                return -1073741771  # STATUS_OBJECT_NAME_COLLISION
            publication = patch.object(copy_storage, '_rename_verified_child_windows',
                                       side_effect=collide_at_publication)
        elif sys.platform.startswith('linux'):
            publication = patch.object(profiles.os, 'fsync', side_effect=replace_destination_and_fail)
        else:
            with self.assertRaises(profiles.ProfileError):
                self.store.export_profile(self.profile, destination)
            self.assertFalse(destination.exists())
            return
        with publication:
            with self.assertRaises(profiles.ProfileError):
                self.store.export_profile(self.profile, destination)
        self.assertEqual(destination.read_bytes(), foreign)

    @unittest.skipUnless(sys.platform.startswith('linux'),
                         'Private mode bits are validated on Linux; other platforms fail closed.')
    def test_export_retains_private_file_permissions(self):
        destination = self.root / 'controls.ktinput.json'
        self.store.export_profile(self.profile, destination)
        self.assertEqual(destination.stat().st_mode & 0o777, 0o600)

    def test_import_rejects_foreign_schema_wrong_game_and_oversized_file(self):
        path = self.root / 'portable.json'
        payload = {'schema': profiles.SCHEMA, 'kind': 'controller-profile',
                   'profile': profiles._encode_profile(self.profile)}
        variants = [
            b'{"schema":9,"kind":"controller-profile","profile":{}}',
            (json.dumps({**payload, 'other': True})).encode(),
        ]
        wrong = profiles._encode_profile(self.profile)
        wrong['game_id'] = 'dw7xl_ps3'
        variants.append(json.dumps({'schema': 1, 'kind': 'controller-profile',
                                    'profile': wrong}).encode())
        for raw in variants:
            path.write_bytes(raw)
            with self.subTest(raw=raw[:30]), self.assertRaises(profiles.ProfileError):
                self.store.import_profile(path)
        path.write_bytes(b' ' * (profiles.MAX_PROFILE_BYTES + 1))
        with self.assertRaises(profiles.ProfileError):
            self.store.import_profile(path)

    def test_import_rejects_a_lone_surrogate_before_tk_can_render_it(self):
        path = self.root / 'surrogate-profile.json'
        payload = {'schema': profiles.SCHEMA, 'kind': 'controller-profile',
                   'profile': profiles._encode_profile(self.profile)}
        payload['profile']['name'] = 'Bad name \ud800'
        path.write_text(json.dumps(payload), encoding='utf-8')
        with self.assertRaises(profiles.ProfileError):
            self.store.import_profile(path)

    def test_failed_atomic_store_replacement_preserves_original_and_cleans_temp(self):
        self.store.save_profile(self.profile)
        original = self.store.path.read_bytes()
        replacement = profiles.create_from_preset('dw8xl', 'controller_xbox', 'New controls')
        real_replace = os.replace

        def fail_main(source, destination):
            if Path(destination) == self.store.path:
                raise PermissionError('Settings are read-only')
            return real_replace(source, destination)

        with patch.object(profiles.os, 'replace', side_effect=fail_main):
            with self.assertRaises(profiles.ProfileError):
                self.store.save_profile(replacement)
        self.assertEqual(self.store.path.read_bytes(), original)
        self.assertEqual(profiles._decode_store(self.store.backup_path.read_bytes()), (self.profile,))
        self.assertEqual(list(self.store.path.parent.glob('*.tmp')), [])
        self.assertEqual(list(self.store.path.parent.glob(f'.{self.store.path.name}.*.tmp')), [])

    def test_failed_atomic_store_cleanup_preserves_foreign_temporary_replacement(self):
        foreign = b'SYNTHETIC_FOREIGN_TEMPORARY'
        replaced = []

        def replace_and_fail(source, _destination):
            source = Path(source)
            source.unlink()
            source.write_bytes(foreign)
            replaced.append(source)
            raise OSError('synthetic publication failure')

        with patch.object(profiles.os, 'replace', side_effect=replace_and_fail):
            with self.assertRaises(profiles.ProfileError):
                self.store.save_profile(self.profile)
        self.assertEqual(len(replaced), 1)
        self.assertEqual(replaced[0].read_bytes(), foreign)
        self.assertFalse(self.store.path.exists())

    def test_cleanup_retains_creator_identity_until_foreign_replacement_is_preserved(self):
        foreign = b'SYNTHETIC_FOREIGN_TEMPORARY'
        replaced, descriptors = [], []
        cleanup = profiles._unlink_owned

        def replace_and_fail(source, _destination):
            source = Path(source)
            source.unlink()
            source.write_bytes(foreign)
            replaced.append(source)
            raise OSError('synthetic publication failure')

        def inspect_ownership(path, identity, descriptor, snapshot):
            if descriptor is None:
                self.assertEqual(os.name, 'nt')
                self.assertEqual(len(snapshot), 5)
            else:
                held = os.fstat(descriptor)
                self.assertEqual((held.st_dev, held.st_ino), identity)
                # The unlinked creator still owns its inode. The unrelated
                # replacement cannot inherit it even on aggressive allocators.
                self.assertNotEqual(profiles._owned_identity(path), identity)
                descriptors.append(descriptor)
            return cleanup(path, identity, descriptor, snapshot)

        with patch.object(profiles.os, 'replace', side_effect=replace_and_fail), \
                patch.object(profiles, '_unlink_owned', side_effect=inspect_ownership):
            with self.assertRaises(profiles.ProfileError):
                self.store.save_profile(self.profile)
        self.assertEqual(replaced[0].read_bytes(), foreign)
        for descriptor in descriptors:
            with self.assertRaises(OSError):
                os.fstat(descriptor)

    def test_failed_store_cleanup_preserves_inplace_foreign_temporary_changes(self):
        foreign = b'SYNTHETIC_FOREIGN_INPLACE_TEMPORARY'
        replaced = []
        original_open = Path.open

        def replace_and_fail(source, _destination):
            source = Path(source)
            before = profiles._owned_identity(source)
            source.write_bytes(foreign)
            self.assertEqual(profiles._owned_identity(source), before)
            replaced.append(source)
            raise OSError('synthetic publication failure')

        def reject_foreign_read(path, mode='r', *args, **kwargs):
            if path in replaced and 'r' in mode:
                raise AssertionError('Cleanup must not read foreign staging bytes.')
            return original_open(path, mode, *args, **kwargs)

        with patch.object(profiles.os, 'replace', side_effect=replace_and_fail), \
                patch.object(Path, 'open', reject_foreign_read):
            with self.assertRaises(profiles.ProfileError):
                self.store.save_profile(self.profile)
        self.assertEqual(replaced[0].read_bytes(), foreign)
        self.assertFalse(self.store.path.exists())

    def test_changed_temporary_is_not_promoted_into_profile_store(self):
        real_fsync = os.fsync
        foreign = b'SYNTHETIC_FOREIGN_TEMPORARY'
        replaced = []

        def replace_after_sync(descriptor):
            real_fsync(descriptor)
            staged = next(self.store.path.parent.glob(f'.{self.store.path.name}.*.tmp'))
            try:
                staged.unlink()
            except PermissionError:
                self.skipTest('Runtime denies replacing an open staging file')
            staged.write_bytes(foreign)
            replaced.append(staged)

        with patch.object(profiles.os, 'fsync', side_effect=replace_after_sync):
            with self.assertRaises(profiles.ProfileError):
                self.store.save_profile(self.profile)
        self.assertEqual(replaced[0].read_bytes(), foreign)
        self.assertFalse(self.store.path.exists())

    def test_failed_restore_cleanup_preserves_replaced_recovery_file(self):
        self.store.save_profile(self.profile)
        self.store.backup_path.write_bytes(profiles._serialize_store((self.profile,)))
        foreign = b'SYNTHETIC_FOREIGN_RECOVERY'
        replaced = []

        def replace_recovery_and_fail(_destination, _data, **_kwargs):
            recovery = next(self.store.path.parent.glob('*.recovery.*'))
            recovery.unlink()
            recovery.write_bytes(foreign)
            replaced.append(recovery)
            raise profiles.ProfileError('synthetic store failure')

        with patch.object(profiles, '_atomic_write', side_effect=replace_recovery_and_fail):
            with self.assertRaises(profiles.ProfileError):
                self.store.restore_backup()
        self.assertEqual(replaced[0].read_bytes(), foreign)

    def test_failed_restore_cleanup_preserves_inplace_foreign_recovery_changes(self):
        self.store.save_profile(self.profile)
        self.store.backup_path.write_bytes(profiles._serialize_store((self.profile,)))
        original = self.store.path.read_bytes()
        foreign = b'SYNTHETIC_FOREIGN_INPLACE_RECOVERY'
        replaced = []
        original_open = Path.open

        def replace_recovery_and_fail(_destination, _data, **_kwargs):
            recovery = next(self.store.path.parent.glob('*.recovery.*'))
            before = profiles._owned_identity(recovery)
            recovery.write_bytes(foreign)
            self.assertEqual(profiles._owned_identity(recovery), before)
            replaced.append(recovery)
            raise profiles.ProfileError('synthetic store failure')

        def reject_foreign_read(path, mode='r', *args, **kwargs):
            if path in replaced and 'r' in mode:
                raise AssertionError('Cleanup must not read foreign recovery bytes.')
            return original_open(path, mode, *args, **kwargs)

        with patch.object(profiles, '_atomic_write', side_effect=replace_recovery_and_fail), \
                patch.object(Path, 'open', reject_foreign_read):
            with self.assertRaises(profiles.ProfileError):
                self.store.restore_backup()
        self.assertEqual(replaced[0].read_bytes(), foreign)
        self.assertEqual(self.store.path.read_bytes(), original)

    def test_failed_backup_and_rollback_keep_recovery_bytes_but_release_creator_descriptor(self):
        self.store.save_profile(self.profile)
        current = self.store.path.read_bytes()
        backup = profiles._serialize_store((profiles.create_from_preset(
            'dw8xl', 'controller_xbox', 'Backup controls'),))
        self.store.backup_path.write_bytes(backup)
        real_write, real_retain = profiles._atomic_write, profiles._retain_creator
        restores, descriptors = [], []

        def fail_backup_and_rollback(destination, data, **kwargs):
            if Path(destination) == self.store.path and not restores:
                restores.append(destination)
                return real_write(destination, data, **kwargs)
            raise profiles.ProfileError('synthetic backup or rollback failure')

        def record_recovery_descriptor(stream):
            descriptor = real_retain(stream)
            if '.recovery.' in str(stream.name) and descriptor is not None:
                descriptors.append(descriptor)
            return descriptor

        with patch.object(profiles, '_atomic_write', side_effect=fail_backup_and_rollback), \
                patch.object(profiles, '_retain_creator', side_effect=record_recovery_descriptor):
            with self.assertRaisesRegex(profiles.ProfileError, 'preserved at'):
                self.store.restore_backup()
        recovery, = self.store.path.parent.glob('*.recovery.*')
        self.assertEqual(recovery.read_bytes(), current)
        self.assertEqual(self.store.path.read_bytes(), backup)
        self.assertEqual(self.store.backup_path.read_bytes(), backup)
        for descriptor in descriptors:
            with self.assertRaises(OSError):
                os.fstat(descriptor)

    def test_interrupted_restore_keeps_original_current_bytes_until_outcome_is_known(self):
        for interruption in ('main_commit', 'backup_promotion', 'rollback'):
            with self.subTest(interruption=interruption):
                store = profiles.ProfileStore(self.root / interruption / 'controls.json')
                store.save_profile(self.profile)
                current = store.path.read_bytes()
                backup = profiles._serialize_store((profiles.create_from_preset(
                    'dw8xl', 'controller_xbox', 'Backup controls'),))
                store.backup_path.write_bytes(backup)
                real_write = profiles._atomic_write
                main_calls = []

                def interrupt(destination, data, **kwargs):
                    if Path(destination) == store.path:
                        main_calls.append(destination)
                        if len(main_calls) == 1:
                            result = real_write(destination, data, **kwargs)
                            if interruption == 'main_commit':
                                raise KeyboardInterrupt('Interrupted after store commit')
                            return result
                        raise KeyboardInterrupt('Interrupted during rollback')
                    if interruption == 'backup_promotion':
                        raise KeyboardInterrupt('Interrupted during backup promotion')
                    raise profiles.ProfileError('synthetic backup failure')

                with patch.object(profiles, '_atomic_write', side_effect=interrupt):
                    with self.assertRaises(KeyboardInterrupt):
                        store.restore_backup()
                self.assertEqual(store.path.read_bytes(), backup)
                self.assertEqual(store.backup_path.read_bytes(), backup)
                recovery, = store.path.parent.glob('*.recovery.*')
                self.assertEqual(recovery.read_bytes(), current)

    def test_restore_refuses_corrupt_backup_and_preserves_current_store(self):
        self.store.save_profile(self.profile)
        current = self.store.path.read_bytes()
        self.store.backup_path.write_bytes(b'{"schema":2}')
        with self.assertRaises(profiles.ProfileError):
            self.store.restore_backup()
        self.assertEqual(self.store.path.read_bytes(), current)

    def test_failed_restore_keeps_the_original_backup_and_current_store(self):
        self.store.save_profile(self.profile)
        current = self.store.path.read_bytes()
        backup_profile = profiles.create_from_preset('dw8xl', 'controller_xbox', 'Backup profile')
        backup_raw = profiles._serialize_store((backup_profile,))
        self.store.backup_path.write_bytes(backup_raw)
        real_replace = os.replace

        def fail_main(source, destination):
            if Path(destination) == self.store.path:
                raise PermissionError('settings are read-only')
            return real_replace(source, destination)

        with patch.object(profiles.os, 'replace', side_effect=fail_main):
            with self.assertRaises(profiles.ProfileError):
                self.store.restore_backup()
        self.assertEqual(self.store.path.read_bytes(), current)
        self.assertEqual(self.store.backup_path.read_bytes(), backup_raw)
        self.assertEqual(list(self.store.path.parent.glob('*.recovery.*')), [])

    def test_failed_backup_promotion_rolls_back_the_restored_store(self):
        self.store.save_profile(self.profile)
        current = self.store.path.read_bytes()
        backup_profile = profiles.create_from_preset('dw8xl', 'controller_xbox', 'Backup profile')
        backup_raw = profiles._serialize_store((backup_profile,))
        self.store.backup_path.write_bytes(backup_raw)
        real_replace = os.replace

        def fail_backup(source, destination):
            if Path(destination) == self.store.backup_path:
                raise PermissionError('backup location is read-only')
            return real_replace(source, destination)

        with patch.object(profiles.os, 'replace', side_effect=fail_backup):
            with self.assertRaisesRegex(profiles.ProfileError, 'prior state'):
                self.store.restore_backup()
        self.assertEqual(self.store.path.read_bytes(), current)
        self.assertEqual(self.store.backup_path.read_bytes(), backup_raw)
        self.assertEqual(list(self.store.path.parent.glob('*.recovery.*')), [])

    def test_restore_from_valid_backup_can_recover_corrupt_current_store_and_preserves_it(self):
        self.store.save_profile(self.profile)
        backup_raw = self.store.path.read_bytes()
        self.store.backup_path.write_bytes(backup_raw)
        corrupt = b'{"schema":99,"private":"keep for recovery"}'
        self.store.path.write_bytes(corrupt)
        self.assertEqual(self.store.restore_backup(), (self.profile,))
        self.assertEqual(self.store.path.read_bytes(), backup_raw)
        self.assertEqual(self.store.path.with_name(self.store.path.name + '.invalid').read_bytes(), corrupt)

    def test_restore_does_not_overwrite_an_existing_invalid_quarantine(self):
        self.store.save_profile(self.profile)
        backup_raw = self.store.path.read_bytes()
        self.store.backup_path.write_bytes(backup_raw)
        corrupt = b'{"schema":99,"private":"new invalid data"}'
        prior_quarantine = b'{"schema":98,"private":"previous invalid data"}'
        quarantine_path = self.store.path.with_name(self.store.path.name + '.invalid')
        quarantine_path.write_bytes(prior_quarantine)
        self.store.path.write_bytes(corrupt)

        self.assertEqual(self.store.restore_backup(), (self.profile,))
        self.assertEqual(quarantine_path.read_bytes(), prior_quarantine)
        quarantined = list(self.store.path.parent.glob(self.store.path.name + '.invalid.*'))
        self.assertEqual(len(quarantined), 1)
        self.assertEqual(quarantined[0].read_bytes(), corrupt)


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'A graphical display is required.')
class ControllerProfileWorkspaceTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.root.destroy)
        self.store = profiles.ProfileStore(Path(self.directory.name) / 'profiles.json')
        self.store.save_profile(profiles.create_from_preset('dw8xl', 'keyboard_wasd', 'My keyboard'))
        self.workspace = ControllerProfileWorkspace(self.root, self.root, self.store)
        self.workspace.frame.pack(fill='both', expand=True)
        self.workspace.game_choice.set(self.workspace._game_label('dw8xl'))
        self.workspace._select_game()
        self.root.update()

    def test_profile_search_filters_selected_game_and_focus_search_exposes_entry(self):
        self.assertEqual(len(self.workspace.profile_tree.get_children()), 1)
        self.workspace.profile_search.set('missing')
        self.root.update()
        self.assertEqual(len(self.workspace.profile_tree.get_children()), 0)
        self.workspace.profile_search.set('keyboard')
        self.root.update()
        self.assertEqual(len(self.workspace.profile_tree.get_children()), 1)
        # Xvfb has no window manager to activate the test window.
        self.root.focus_force()
        self.workspace.focus_search()
        self.root.update()
        self.assertIs(self.root.focus_get(), self.workspace.search_entry)
        self.assertIn('This app stores the profile only', self.workspace.status.get())

    def test_workspace_uses_the_shell_language_when_first_opened(self):
        workspace = ControllerProfileWorkspace(self.root, self.root, self.store, language='de')
        self.assertEqual(workspace.language, 'de')
        self.assertEqual(workspace.title_label.cget('text'), 'Controller- und Eingabeprofile')
        workspace._edit_dialog(None)
        dialog = next(widget for widget in self.root.winfo_children() if isinstance(widget, tk.Toplevel))
        self.assertEqual(dialog.title(), 'Neues Controllerprofil')
        self.assertEqual(workspace._preset_id_from_label('Tastaturvorlage WASD'), 'keyboard_wasd')
        self.assertEqual(workspace._layout_label('generic'), 'Allgemein')
        self.assertEqual(workspace._layout_id_from_label('PlayStation-Beschriftungen'), 'playstation')
        descendants = list(dialog.winfo_children())
        widgets = []
        while descendants:
            widget = descendants.pop()
            widgets.append(widget)
            descendants.extend(widget.winfo_children())
        self.assertTrue(any(isinstance(widget, ttk.Entry) and widget.get() == 'Leeres Profil'
                            for widget in widgets))
        layout_selector = next(widget for widget in widgets if isinstance(widget, ttk.Combobox)
                               and 'Allgemein' in widget.cget('values'))
        self.assertEqual(layout_selector.get(), 'Allgemein')
        dialog.destroy()

    def test_adding_multiple_bindings_appends_instead_of_replacing(self):
        self.workspace._edit_dialog(None)
        self.root.update()
        dialog = next(widget for widget in self.root.winfo_children() if isinstance(widget, tk.Toplevel))
        descendants = list(dialog.winfo_children())
        widgets = []
        while descendants:
            widget = descendants.pop()
            widgets.append(widget)
            descendants.extend(widget.winfo_children())
        fields = next(widget for widget in widgets if isinstance(widget, ttk.Frame)
                      and sum(isinstance(child, ttk.Entry) for child in widget.winfo_children()) == 3)
        entries = sorted((widget for widget in fields.winfo_children() if isinstance(widget, ttk.Entry)),
                         key=lambda widget: int(widget.grid_info()['column']))
        tree = next(widget for widget in widgets if isinstance(widget, ttk.Treeview))
        add_button = next(widget for widget in widgets if isinstance(widget, ttk.Button)
                          and widget.cget('text') == 'Add / update binding')
        action, keyboard, controller = entries[-3:]
        action.insert(0, 'Move up')
        keyboard.insert(0, 'W')
        add_button.invoke()
        self.assertEqual(len(tree.get_children()), 1)
        self.assertEqual(tree.selection(), ())
        action.insert(0, 'Confirm')
        keyboard.insert(0, 'Enter')
        add_button.invoke()
        self.assertEqual(len(tree.get_children()), 2)
        self.assertEqual(tree.item('0', 'text'), 'Move up')
        self.assertEqual(tree.item('1', 'text'), 'Confirm')
        dialog.destroy()

    def test_starter_selection_updates_only_the_automatic_profile_name(self):
        self.workspace._edit_dialog(None)
        self.root.update()
        dialog = next(widget for widget in self.root.winfo_children() if isinstance(widget, tk.Toplevel))
        descendants = list(dialog.winfo_children())
        widgets = []
        while descendants:
            widget = descendants.pop()
            widgets.append(widget)
            descendants.extend(widget.winfo_children())
        header = next(widget for widget in widgets if isinstance(widget, ttk.Frame)
                      and sum(isinstance(child, ttk.Entry) and not isinstance(child, ttk.Combobox)
                              for child in widget.winfo_children()) == 1
                      and any(isinstance(child, ttk.Combobox) for child in widget.winfo_children()))
        profile_name = next(widget for widget in header.winfo_children() if isinstance(widget, ttk.Entry))
        starter = next(widget for widget in widgets if isinstance(widget, ttk.Combobox)
                       and 'Keyboard WASD starter' in widget.cget('values'))
        starter.set('Keyboard WASD starter')
        starter.event_generate('<<ComboboxSelected>>')
        self.root.update()
        self.assertEqual(profile_name.get(), 'Keyboard WASD starter')
        profile_name.delete(0, 'end')
        profile_name.insert(0, 'My custom controls')
        starter.set('Nintendo label starter')
        starter.event_generate('<<ComboboxSelected>>')
        self.root.update()
        self.assertEqual(profile_name.get(), 'My custom controls')
        dialog.destroy()

    def test_edit_preserves_an_imported_custom_preset_identity(self):
        custom = profiles.create_profile(
            'dw8xl', 'My custom notes', preset_id='custom',
            bindings=(profiles.Binding('Guard', 'G', 'LB'),))
        self.store.save_profile(custom)
        self.workspace._edit_dialog(custom)
        self.root.update()

        pending = list(self.root.winfo_children())
        dialog = next(widget for widget in pending if isinstance(widget, tk.Toplevel))
        pending = list(dialog.winfo_children())
        descendants = []
        while pending:
            widget = pending.pop()
            pending.extend(widget.winfo_children())
            descendants.append(widget)
        preset_selectors = [widget for widget in descendants
                            if isinstance(widget, ttk.Combobox)
                            and str(widget.cget('state')) == 'disabled']
        self.assertEqual(len(preset_selectors), 1)
        self.assertEqual(preset_selectors[0].get(), self.workspace._preset_label('custom'))
        save_buttons = [widget for widget in descendants
                        if isinstance(widget, ttk.Button) and widget.cget('text') == 'Save profile']
        self.assertEqual(len(save_buttons), 1)
        save_buttons[0].invoke()

        updated = next(profile for profile in self.store.list_profiles('dw8xl')
                       if profile.profile_id == custom.profile_id)
        self.assertEqual(updated.preset_id, 'custom')


if __name__ == '__main__':
    unittest.main()
