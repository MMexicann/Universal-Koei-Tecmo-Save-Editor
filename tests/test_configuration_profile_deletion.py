"""Profile deletion retains records changed while their identity is checked."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.shared import configuration_manager as config


class ProfileDeletionSafetyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        source = self.root / 'ArlandDX_Settings.ini'
        source.write_bytes(b'[Window]\nFullScreen=0\n')
        self.document = config.inspect_config(source, 'arland_rorona_dx')
        self.profiles = self.root / 'profiles'
        self.profile = config.create_profile(self.document, 'Windowed', self.profiles)
        self.path = self.profiles / (self.profile.id + '.json')
        self.original = self.path.read_bytes()

    def test_replacement_during_profile_parse_is_retained(self):
        native_parse = config._parse_profile
        foreign = self.root / 'foreign-record.json'
        foreign.write_bytes(self.original)
        replacement_identity = (foreign.stat().st_dev, foreign.stat().st_ino)

        def replace_after_parse(raw, expected_id=None):
            result = native_parse(raw, expected_id)
            foreign.replace(self.path)
            return result

        with patch.object(config, '_parse_profile', side_effect=replace_after_parse):
            with self.assertRaises(config.ConfigurationChangedError):
                config.delete_profile(self.profile.id, self.profiles)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual((self.path.stat().st_dev, self.path.stat().st_ino), replacement_identity)

    def test_same_inode_content_change_during_parse_is_retained(self):
        native_parse = config._parse_profile
        before = self.path.stat()
        changed = self.original.replace(b'Windowed', b'Changed!')
        self.assertNotEqual(changed, self.original)
        self.assertEqual(len(changed), len(self.original))

        def change_after_parse(raw, expected_id=None):
            result = native_parse(raw, expected_id)
            self.path.write_bytes(changed)
            os.utime(self.path, ns=(before.st_atime_ns, before.st_mtime_ns))
            return result

        with patch.object(config, '_parse_profile', side_effect=change_after_parse):
            with self.assertRaises(config.ConfigurationChangedError):
                config.delete_profile(self.profile.id, self.profiles)
        self.assertEqual(self.path.read_bytes(), changed)
        self.assertEqual(self.path.stat().st_ino, before.st_ino)

    def test_replacement_after_record_read_is_retained(self):
        native_read = config._read_bounded_file
        foreign = self.root / 'foreign-readback.json'
        foreign.write_bytes(b'UNRELATED_RECORD_AFTER_READ')
        replaced = []

        def replace_after_read(path, limit, **kwargs):
            result = native_read(path, limit, **kwargs)
            if Path(path) == self.path and not replaced:
                foreign.replace(self.path)
                replaced.append(True)
            return result

        with patch.object(config, '_read_bounded_file', side_effect=replace_after_read):
            with self.assertRaises(config.ConfigurationChangedError):
                config.delete_profile(self.profile.id, self.profiles)
        self.assertEqual(replaced, [True])
        self.assertEqual(self.path.read_bytes(), b'UNRELATED_RECORD_AFTER_READ')

    def test_unchanged_selected_profile_is_removed_and_other_records_remain(self):
        other = config.create_profile(self.document, 'Unrelated', self.profiles)
        other_path = self.profiles / (other.id + '.json')
        unrelated = other_path.read_bytes()
        self.assertTrue(config.delete_profile(self.profile.id, self.profiles))
        self.assertFalse(self.path.exists())
        self.assertEqual(other_path.read_bytes(), unrelated)
        self.assertEqual(config.list_profiles(self.profiles), (other,))


if __name__ == '__main__':
    unittest.main()
