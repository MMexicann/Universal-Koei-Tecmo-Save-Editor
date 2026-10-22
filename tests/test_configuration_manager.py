"""Regression checks for the explicitly cataloged Arland DX settings files."""
import json
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from koei_editor.shared import configuration_manager as config


GAME = 'arland_rorona_dx'


def arland_game_fixture():
    """Synthetic text only; not copied from an installed game."""
    return (b'; preserved opaque comment \xff\r\n'
            b'[Window]\r\n'
            b'FullScreen = 0  \r\n'
            b'CustomWindowValue = keep-me\r\n'
            b'[Lang]\n'
            b'Language = 2\n'
            b'[Graphics]\r'
            b'Outline=1\r'
            b'ScreenWidth = 1920\r'
            b'ScreenHeight = 1080\r'
            b'Unmapped = opaque\r')


def arland_mod_fixture():
    """Synthetic text only; keys are limited to the reviewed public adapter."""
    return (b'; preserved non-ASCII comment \xfe\r\n'
            b'[Rendering]\r\n'
            b'ShadowMultiplier = 4\r\n'
            b'SMAA = yes\r\n'
            b'Sharpen = 60\r\n'
            b'Font = custom-value\r\n'
            b'DisplayWidth = monitor-specific\r\n'
            b'[Battle]\r\n'
            b'BattleCutInShadows = false\r\n'
            b'BattleCutInDimming = 1\r\n'
            b'[Startup]\r\n'
            b'SkipLogos = TRUE\r\n'
            b'SkipIntroMovie = 0\r\n'
            b'[Launcher]\r\n'
            b'SkipLauncher = no\r\n'
            b'[Diagnostics]\r\n'
            b'VerboseLogging = 0\r\n'
            b'[Debug]\r\n'
            b'FastBattleTransition = 1\r\n')


class ConfigurationManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.backups = self.root / 'backups'
        self.profiles = self.root / 'profiles'

    def tearDown(self):
        self.temporary.cleanup()

    def _write(self, name, raw):
        path = self.root / name
        path.write_bytes(raw)
        return path

    def _inspect_game(self, raw=None, game_id=GAME):
        return config.inspect_config(self._write('ArlandDX_Settings.ini', raw or arland_game_fixture()), game_id)

    def _inspect_mod(self, raw=None, game_id=GAME):
        return config.inspect_config(self._write('arland-fix.ini', raw or arland_mod_fixture()), game_id)

    def test_catalog_is_exact_and_game_ini_surgical_edits_preserve_every_other_byte(self):
        self.assertEqual(tuple(game.id for game in config.SUPPORTED_GAMES),
                         ('arland_rorona_dx', 'arland_totori_dx', 'arland_meruru_dx'))
        self.assertEqual({item.id for item in config.SUPPORTED_FORMATS},
                         {config.FORMAT_ID, config.MOD_FORMAT_ID})
        for supported_format in config.SUPPORTED_FORMATS:
            self.assertIn('96a4506892de3284a8adc78a4b6a96d67e8bbf59',
                          supported_format.evidence_url)
        raw = arland_game_fixture()
        document = self._inspect_game(raw)
        self.assertEqual(document.format_id, config.FORMAT_ID)
        fields = {item.id: item for item in config.supported_settings(document)}
        self.assertEqual(fields['fullscreen'].value, 0)
        self.assertEqual(fields['language'].display_value, 'English')
        self.assertEqual(fields['outline'].value, 1)
        self.assertEqual(fields['screen_width'].value, 1920)
        self.assertFalse(fields['screen_width'].writable)
        self.assertEqual(config.serialize_config(document, {}), raw)

        updated = config.serialize_config(document, {'fullscreen': 1, 'language': 4})
        expected = raw.replace(b'FullScreen = 0', b'FullScreen = 1').replace(b'Language = 2', b'Language = 4')
        self.assertEqual(updated, expected)
        self.assertIn(b'\xff', updated)
        self.assertIn(b'CustomWindowValue = keep-me\r\n', updated)
        self.assertIn(b'Unmapped = opaque\r', updated)
        self.assertEqual(config.inspect_config(self._write('ArlandDX_Settings.ini', updated), GAME).sha256,
                         config._digest(updated))

    def test_mod_ini_supports_only_cataloged_values_and_preserves_boolean_encoding(self):
        raw = arland_mod_fixture()
        document = self._inspect_mod(raw)
        self.assertEqual(document.format_id, config.MOD_FORMAT_ID)
        fields = {item.id: item for item in config.supported_settings(document)}
        self.assertEqual(fields['mod_smaa'].value, 1)
        self.assertEqual(fields['mod_battle_cutin_shadows'].value, 0)
        self.assertEqual(fields['mod_battle_cutin_dimming'].value, 1)
        self.assertEqual(fields['mod_sharpen'].choices,
                         ((0, '0'), (30, '30'), (60, '60'), (100, '100')))
        self.assertNotIn('font', fields)
        self.assertNotIn('mod_fast_battle_transition', fields)
        self.assertNotIn('mod_display_width', fields)

        changes = {'mod_shadow_multiplier': 8, 'mod_smaa': 0,
                   'mod_battle_cutin_shadows': 1, 'mod_skip_intro_movie': 1,
                   'mod_skip_logos': 0,
                   'mod_verbose_logging': 1}
        updated = config.serialize_config(document, changes)
        self.assertIn(b'ShadowMultiplier = 8\r\n', updated)
        self.assertIn(b'SMAA = no\r\n', updated)
        self.assertIn(b'BattleCutInShadows = true\r\n', updated)
        self.assertIn(b'SkipIntroMovie = 1\r\n', updated)
        self.assertIn(b'SkipLogos = FALSE\r\n', updated)
        self.assertIn(b'VerboseLogging = 1\r\n', updated)
        for opaque in (b'\xfe', b'Font = custom-value\r\n', b'DisplayWidth = monitor-specific\r\n',
                       b'FastBattleTransition = 1\r\n'):
            self.assertIn(opaque, updated)
        self.assertEqual(config.serialize_config(document, {}), raw)

    def test_only_exact_filenames_and_known_game_profiles_are_accepted(self):
        wrong_extension = self._write('settings.ini', arland_game_fixture())
        with self.assertRaises(config.UnsupportedConfigurationError):
            config.inspect_config(wrong_extension, GAME)
        unknown_title_path = self._write('ArlandDX_Settings.ini', arland_game_fixture())
        with self.assertRaises(config.UnsupportedConfigurationError):
            config.inspect_config(unknown_title_path, 'dynasty_warriors_8')
        unrecognized = self._write('ArlandDX_Settings.ini', b'[Unknown]\nSetting=1\n')
        before = unrecognized.read_bytes()
        with self.assertRaises(config.UnsupportedConfigurationError):
            config.inspect_config(unrecognized, GAME)
        self.assertEqual(unrecognized.read_bytes(), before)

    def test_ambiguous_and_oversized_files_are_rejected_without_writes(self):
        duplicate = self._write('ArlandDX_Settings.ini',
                                b'[Window]\nFullScreen=0\n[Window]\nFullScreen=1\n')
        with self.assertRaises(config.UnsupportedConfigurationError):
            config.inspect_config(duplicate, GAME)
        oversized = self._write('arland-fix.ini', b';' + b'x' * config.MAX_CONFIG_BYTES)
        with self.assertRaises(config.UnsupportedConfigurationError):
            config.inspect_config(oversized, GAME)
        self.assertEqual(oversized.stat().st_size, config.MAX_CONFIG_BYTES + 1)

    def test_unknown_values_are_read_only_and_missing_keys_are_never_created(self):
        document = self._inspect_game(b'[Window]\nFullScreen=9\n')
        self.assertEqual(document.fields[0].value, 9)
        self.assertFalse(document.fields[0].writable)
        with self.assertRaises(config.ConfigurationError):
            config.serialize_config(document, {'fullscreen': 1})
        with self.assertRaises(config.IncompatibleConfigurationError):
            config.serialize_config(document, {'outline': 1})

        document = self._inspect_game(b'[Window]\nFullScreen=0\n')
        self.assertEqual(config.serialize_config(document, {'fullscreen': 1}),
                         b'[Window]\nFullScreen=1\n')
        with self.assertRaises(config.IncompatibleConfigurationError):
            config.serialize_config(document, {'language': 2})

        mod = self._inspect_mod(b'[Rendering]\nSMAA=maybe\nSharpen=80\n')
        mod_fields = {item.id: item for item in mod.fields}
        self.assertFalse(mod_fields['mod_smaa'].writable)
        self.assertFalse(mod_fields['mod_sharpen'].writable)
        with self.assertRaises(config.ConfigurationError):
            config.serialize_config(mod, {'mod_smaa': 1})

    def test_inconsistent_public_document_metadata_cannot_redirect_a_write(self):
        document = self._inspect_game()
        location = document._locations[0]
        redirected = replace(document, _locations=(replace(location, start=0),) + document._locations[1:])
        with self.assertRaises(config.IncompatibleConfigurationError):
            config.serialize_config(redirected, {'fullscreen': 1})

    def test_comparison_reports_supported_fields_and_unmapped_byte_differences(self):
        left = self._inspect_game(arland_game_fixture())
        right_raw = arland_game_fixture().replace(b'FullScreen = 0', b'FullScreen = 1')
        right_raw = right_raw.replace(b'Unmapped = opaque', b'Unmapped = changed')
        right = self._inspect_game(right_raw)
        comparison = config.compare_configs(left, right)
        self.assertTrue(comparison.compatible)
        self.assertTrue(comparison.same_game)
        self.assertEqual(tuple(item.field_id for item in comparison.changed_fields), ('fullscreen',))
        self.assertTrue(comparison.opaque_difference)

        only_setting_change = self._inspect_game(arland_game_fixture().replace(
            b'FullScreen = 0', b'FullScreen = 1'))
        self.assertFalse(config.compare_configs(left, only_setting_change).opaque_difference)

        present = self._inspect_game(b'[Window]\nFullScreen=0\n[Lang]\nLanguage=2\n')
        absent = self._inspect_game(b'[Window]\n[Lang]\nLanguage=2\n')
        missing_key = config.compare_configs(present, absent)
        self.assertEqual(tuple(item.field_id for item in missing_key.changed_fields), ('fullscreen',))
        self.assertFalse(missing_key.opaque_difference)
        opaque_section = self._inspect_game(
            b'[Window]\nFullScreen=0\n[Lang]\nLanguage=2\n[Unknown]\nSetting=keep\n')
        opaque_changed = self._inspect_game(
            b'[Window]\nFullScreen=0\n[Lang]\nLanguage=2\n[Unknown]\nSetting=changed\n')
        self.assertTrue(config.compare_configs(opaque_section, opaque_changed).opaque_difference)

        invalid_left = self._inspect_game(
            b'[Window]\nFullScreen=maybe\n[Lang]\nLanguage=2\n')
        invalid_right = self._inspect_game(
            b'[Window]\nFullScreen=maybe2\n[Lang]\nLanguage=2\n')
        invalid_comparison = config.compare_configs(invalid_left, invalid_right)
        self.assertEqual(tuple(item.field_id for item in invalid_comparison.changed_fields), ('fullscreen',))
        self.assertFalse(invalid_comparison.opaque_difference)

        known_empty_section = self._inspect_game(b'[Window]\n[Lang]\nLanguage=2\n')
        whitespace_unknown_section = self._inspect_game(b'[Window ]\n[Lang]\nLanguage=2\n')
        self.assertTrue(config.compare_configs(
            known_empty_section, whitespace_unknown_section).opaque_difference)

        other_title_path = self.root / 'other-title' / 'ArlandDX_Settings.ini'
        other_title_path.parent.mkdir()
        other_title_path.write_bytes(arland_game_fixture())
        other_title = config.inspect_config(other_title_path, 'arland_totori_dx')
        self.assertTrue(config.compare_configs(left, other_title).compatible)
        self.assertFalse(config.compare_configs(left, other_title).same_game)

    def test_profiles_are_path_free_bounded_and_strictly_compatible(self):
        document = self._inspect_game()
        profile = config.create_profile(document, 'Windowed English', self.profiles)
        self.assertEqual(profile.game_id, GAME)
        self.assertEqual(profile.settings, {'fullscreen': 0, 'language': 2, 'outline': 1})
        profile_bytes = (self.profiles / f'{profile.id}.json').read_bytes()
        self.assertNotIn(str(document.path).encode(), profile_bytes)
        self.assertEqual(config.list_profiles(self.profiles), (profile,))
        self.assertEqual(config.apply_profile(document, profile), profile.settings)
        self.assertTrue(config.compatibility_check(document, GAME, config.FORMAT_ID, 1).compatible)
        self.assertFalse(config.compatibility_check(document, 'arland_totori_dx').compatible)

        wrong_game_path = self.root / 'other-title' / 'ArlandDX_Settings.ini'
        wrong_game_path.parent.mkdir()
        wrong_game_path.write_bytes(arland_game_fixture())
        wrong_game = config.inspect_config(wrong_game_path, 'arland_totori_dx')
        with self.assertRaises(config.IncompatibleConfigurationError):
            config.apply_profile(wrong_game, profile)

        mod = self._inspect_mod()
        with self.assertRaises(config.IncompatibleConfigurationError):
            config.apply_profile(mod, profile)
        self.assertTrue(config.delete_profile(profile.id, self.profiles))
        self.assertEqual(config.list_profiles(self.profiles), ())

    def test_mod_profile_uses_mod_format_and_rejects_game_ini_profile(self):
        document = self._inspect_mod()
        profile = config.create_profile(document, 'Mod visual settings', self.profiles)
        self.assertEqual(profile.format_id, config.MOD_FORMAT_ID)
        self.assertEqual(config.list_profiles(self.profiles), (profile,))
        self.assertEqual(config.apply_profile(document, profile), profile.settings)
        game_doc = self._inspect_game()
        with self.assertRaises(config.IncompatibleConfigurationError):
            config.apply_profile(game_doc, profile)

    def test_save_auto_backup_and_restore_are_exact_for_both_formats(self):
        for is_mod in (False, True):
            with self.subTest(format='mod' if is_mod else 'game'):
                backup_dir = self.backups / ('mod' if is_mod else 'game')
                raw = arland_mod_fixture() if is_mod else arland_game_fixture()
                document = self._inspect_mod(raw) if is_mod else self._inspect_game(raw)
                field_id, new_value = (('mod_smaa', 0) if is_mod else ('fullscreen', 1))
                original = document.raw
                saved = config.save_config(document, {field_id: new_value}, backup_dir)
                self.assertNotEqual(saved.raw, original)
                values = {item.id: item.value for item in saved.fields}
                self.assertEqual(values[field_id], new_value)
                backups = config.list_backups(backup_dir, GAME)
                self.assertEqual(len(backups), 1)
                backup_id = backups[0].id
                restored = config.restore_backup(saved, backup_id, backup_dir)
                self.assertEqual(restored.raw, original)
                self.assertEqual(restored.sha256, config._digest(original))
                self.assertEqual(len(config.list_backups(backup_dir, GAME)), 2)

    def test_backup_restore_rejects_wrong_title_and_corrupt_record(self):
        document = self._inspect_game()
        target_before = document.path.read_bytes()
        backup = config.create_backup(document, self.backups)
        other_path = self.root / 'other-title' / 'ArlandDX_Settings.ini'
        other_path.parent.mkdir()
        other_path.write_bytes(arland_game_fixture())
        other = config.inspect_config(other_path, 'arland_totori_dx')
        other_before = other.path.read_bytes()
        with self.assertRaises(config.IncompatibleConfigurationError):
            config.restore_backup(other, backup.id, self.backups)
        self.assertEqual(other.path.read_bytes(), other_before)
        self.assertEqual(document.path.read_bytes(), target_before)
        self.assertEqual(config.list_backups(self.backups), (backup,))

        backup_path = self.backups / f'{backup.id}.json'
        original_record = backup_path.read_bytes()
        value = json.loads(original_record)
        value['sha256'] = '0' * 64
        backup_path.write_text(json.dumps(value), encoding='ascii')
        self.assertEqual(config.list_backups(self.backups), ())
        with self.assertRaises(config.ConfigurationError):
            config.restore_backup(document, backup.id, self.backups)
        self.assertEqual(document.path.read_bytes(), target_before)
        self.assertEqual(config.list_backups(self.backups), ())

        value = json.loads(original_record)
        value['format_id'] = 'unlisted_format'
        backup_path.write_text(json.dumps(value), encoding='ascii')
        self.assertEqual(config.list_backups(self.backups), ())
        with self.assertRaises(config.ConfigurationError):
            config.restore_backup(document, backup.id, self.backups)
        self.assertEqual(document.path.read_bytes(), target_before)
        self.assertEqual(config.list_backups(self.backups), ())

    def test_stale_source_is_never_overwritten_and_does_not_create_backup(self):
        path = self._write('ArlandDX_Settings.ini', arland_game_fixture())
        document = config.inspect_config(path, GAME)
        external = document.raw.replace(b'Unmapped = opaque', b'Unmapped = external')
        path.write_bytes(external)
        with self.assertRaises(config.ConfigurationChangedError):
            config.create_profile(document, 'stale profile', self.profiles)
        self.assertFalse(self.profiles.exists())
        with self.assertRaises(config.ConfigurationChangedError):
            config.save_config(document, {'fullscreen': 1}, self.backups)
        self.assertEqual(path.read_bytes(), external)
        self.assertEqual(config.list_backups(self.backups), ())


if __name__ == '__main__':
    unittest.main()
