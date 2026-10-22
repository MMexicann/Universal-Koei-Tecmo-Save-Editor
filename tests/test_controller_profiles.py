"""App-owned controller profile data never reaches native game or Steam files."""
import json
import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.shared import controller_profiles as profiles
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
            with patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
                path = profiles.default_store_path()
        self.assertEqual(path, Path(directory) / 'UniversalKoeiTecmoSaveEditor' /
                         'controller_profiles.json')
        self.assertNotIn('Steam', str(path))


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
        with patch.object(profiles.os, 'fsync', side_effect=OSError('disk full')):
            with self.assertRaises(profiles.ProfileError):
                self.store.export_profile(self.profile, destination)
        self.assertFalse(destination.exists())
        self.assertEqual(list(destination.parent.iterdir()), [])

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
        self.workspace.focus_search()
        self.root.update()
        self.assertIs(self.root.focus_get(), self.workspace.search_entry)
        self.assertIn('do not change game files or Steam Input', self.workspace.status.get())

    def test_workspace_uses_the_shell_language_when_first_opened(self):
        workspace = ControllerProfileWorkspace(self.root, self.root, self.store, language='de')
        self.assertEqual(workspace.language, 'de')
        self.assertEqual(workspace.title_label.cget('text'), 'Controller- und Eingabeprofile')
        workspace._edit_dialog(None)
        dialog = next(widget for widget in self.root.winfo_children() if isinstance(widget, tk.Toplevel))
        self.assertEqual(dialog.title(), 'Neues Controllerprofil')
        self.assertEqual(workspace._preset_id_from_label('Tastaturvorlage WASD'), 'keyboard_wasd')
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
        descendants = list(dialog.winfo_children())
        preset_selector = None
        while descendants:
            widget = descendants.pop()
            descendants.extend(widget.winfo_children())
            if isinstance(widget, ttk.Combobox) and widget.cget('state') == 'disabled':
                preset_selector = widget
            if isinstance(widget, ttk.Button) and widget.cget('text') == 'Save profile':
                self.assertIsNotNone(preset_selector)
                self.assertEqual(preset_selector.get(), self.workspace._preset_label('custom'))
                widget.invoke()
                break
        else:
            self.fail('Edit dialog did not expose its save action.')

        updated = next(profile for profile in self.store.list_profiles('dw8xl')
                       if profile.profile_id == custom.profile_id)
        self.assertEqual(updated.preset_id, 'custom')


if __name__ == '__main__':
    unittest.main()
