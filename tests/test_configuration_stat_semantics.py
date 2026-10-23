"""Windows path birthtime and handle ChangeTime remain separate freshness clocks."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.shared import configuration_manager as config


class _CtimeOnlyStat:
    def __init__(self, original, ctime_ns):
        self.original = original
        self.st_ctime_ns = ctime_ns

    def __getattr__(self, name):
        return getattr(self.original, name)


class ConfigurationStatSemanticsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / 'ArlandDX_Settings.ini'
        self.raw = b'[Window]\nFullScreen=0\n'
        self.source.write_bytes(self.raw)
        self.game = 'arland_rorona_dx'

    def test_distinct_handle_ctime_allows_inspect_save_backup_restore_and_delete(self):
        native_fstat = os.fstat
        offsets = []
        offset = 123456789

        def handle_stat(descriptor):
            info = native_fstat(descriptor)
            offsets.append(offset)
            # Alter only handle ctime. Path lstat and every shared stable field
            # remain genuine; the two APIs may expose different Windows clocks.
            return _CtimeOnlyStat(info, info.st_ctime_ns + offset)

        with patch.object(config.os, 'fstat', side_effect=handle_stat):
            document = config.inspect_config(self.source, self.game)
            backup = config.create_backup(document, self.root / 'backups')
            profile = config.create_profile(document, 'Windowed', self.root / 'profiles')
            saved = config.save_config(document, {'fullscreen': 1}, self.root / 'backups')
            restored = config.restore_backup(saved, backup.id, self.root / 'backups')
            self.assertEqual(restored.raw, self.raw)
            self.assertTrue(config.delete_profile(profile.id, self.root / 'profiles'))
        self.assertTrue(offsets)
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertFalse((self.root / 'profiles' / (profile.id + '.json')).exists())

    def test_change_between_source_handle_snapshots_is_still_rejected(self):
        native_open, native_fstat = os.open, os.fstat
        handles, calls = [], []

        def source_open(path, *args, **kwargs):
            descriptor = native_open(path, *args, **kwargs)
            if Path(path) == self.source:
                handles.append(descriptor)
            return descriptor

        def handle_stat(descriptor):
            info = native_fstat(descriptor)
            if descriptor not in handles:
                return info
            calls.append(info)
            return _CtimeOnlyStat(info, info.st_ctime_ns + 123456789 + int(len(calls) > 1))

        with patch.object(config.os, 'open', side_effect=source_open), \
                patch.object(config.os, 'fstat', side_effect=handle_stat):
            with self.assertRaisesRegex(config.ConfigurationChangedError, 'changed while being read'):
                config.inspect_config(self.source, self.game)
        self.assertEqual(len(handles), 1, 'The canonical source handle must be targeted')
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_change_between_profile_path_snapshots_still_prevents_delete(self):
        document = config.inspect_config(self.source, self.game)
        profiles = self.root / 'profiles'
        profile = config.create_profile(document, 'Windowed', profiles)
        path = profiles / (profile.id + '.json')
        original = path.read_bytes()
        native_lstat, native_parse = Path.lstat, config._parse_profile
        parsed, changed_paths = [], []

        def parsed_profile(raw, expected_id=None):
            result = native_parse(raw, expected_id)
            parsed.append(True)
            return result

        def path_stat(selected, *args, **kwargs):
            info = native_lstat(selected, *args, **kwargs)
            if selected == path and parsed:
                changed_paths.append(selected)
                return _CtimeOnlyStat(info, info.st_ctime_ns + 1)
            return info

        with patch.object(Path, 'lstat', path_stat), \
                patch.object(config, '_parse_profile', side_effect=parsed_profile):
            with self.assertRaisesRegex(config.ConfigurationChangedError, 'changed during removal'):
                config.delete_profile(profile.id, profiles)
        self.assertEqual(parsed, [True])
        self.assertTrue(changed_paths, 'The canonical profile path must receive the ctime fault')
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(self.source.read_bytes(), self.raw)


if __name__ == '__main__':
    unittest.main()
