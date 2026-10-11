"""Owner context tests use invented account numbers, never player metadata."""
from dataclasses import FrozenInstanceError, replace
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import steam_owner as owner
from koei_editor.shared.save_safety import safe_path


def invented_vdf(account=b'4242'):
    return b'"steam_autocloud.vdf"\r\n{\r\n\t"accountid"\t"' + account + b'"\r\n}\r\n'


class SteamOwnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.save = self.root / 'copy.bin'
        self.save.write_bytes(b'copied game bytes')
        self.sidecar = self.root / owner.OWNER_BASENAME
        self.sidecar.write_bytes(invented_vdf())

    def test_native_shape_private_derivation_immutable_and_redacted(self):
        context = owner.read_owner(self.save)
        self.assertEqual(context.account_id, 4242)
        self.assertEqual(context.steam_id64, owner.STEAM_INDIVIDUAL_BASE + 4242)
        self.assertEqual(context.raw, self.sidecar.read_bytes())
        self.assertEqual(context.basename, owner.OWNER_BASENAME)
        self.assertEqual(len(context.sha256), 64)
        self.assertEqual(repr(context), '<SteamOwnerContext>')
        self.assertNotIn('4242', str(context))
        self.assertNotIn(str(context.steam_id64), str(context))
        self.assertNotIn(str(context.source), str(context))
        with self.assertRaises(FrozenInstanceError):
            context.raw = b'changed'
        self.assertIs(owner.validate_owner(context), context)

    def test_strict_single_account_shape_and_type_boundaries(self):
        invalid = [b'', b'\0', invented_vdf(b'0'), invented_vdf(b'00'),
                   invented_vdf(b'04242'), invented_vdf(b'-1'), invented_vdf(b'+1'),
                   invented_vdf(b'4294967296'), invented_vdf(b'76561197960269970'),
                   invented_vdf(b'4/242'), invented_vdf(b'4\\242'),
                   invented_vdf(b'4\x00242'), invented_vdf(b'4.242'),
                   invented_vdf().replace(b'accountid', b'SteamID64'),
                   invented_vdf().replace(b'steam_autocloud.vdf', b'steam_autocloud'),
                   invented_vdf().replace(b'}', b'"accountid" "4343" }'),
                   invented_vdf().replace(b'}', b'"foreign" "4343" }'),
                   invented_vdf() + invented_vdf(),
                   b'\xef\xbb\xbf' + invented_vdf(), invented_vdf() + b'\xff']
        for raw in invalid:
            self.sidecar.write_bytes(raw)
            with self.subTest(case=invalid.index(raw)), self.assertRaises(SaveError) as error:
                owner.read_owner(self.save)
            self.assertNotIn('4242', str(error.exception))
            self.assertNotIn('4343', str(error.exception))
        for value in (None, [], {}, bytearray(invented_vdf()), invented_vdf().decode()):
            with self.assertRaises(SaveError):
                owner._account(value)
        for value in (b'1', b'4294967295'):
            self.sidecar.write_bytes(invented_vdf(value))
            self.assertEqual(owner.read_owner(self.save).account_id, int(value))

    def test_size_bound_rejects_oversized_metadata(self):
        raw = invented_vdf()
        self.sidecar.write_bytes(raw + b' ' * (owner.MAX_OWNER_SIZE - len(raw)))
        self.assertEqual(len(owner.read_owner(self.save).raw), owner.MAX_OWNER_SIZE)
        self.sidecar.write_bytes(raw + b' ' * (owner.MAX_OWNER_SIZE + 1 - len(raw)))
        with self.assertRaises(SaveError):
            owner.read_owner(self.save)

    def test_case_preserved_missing_and_ambiguous_metadata(self):
        upper = self.sidecar.with_name('STEAM_AUTOCLOUD.VDF')
        self.sidecar.rename(upper)
        self.assertEqual(owner.read_owner(self.save).basename, upper.name)
        upper.unlink()
        with self.assertRaises(SaveError):
            owner.read_owner(self.save)
        upper.write_bytes(invented_vdf())
        self.sidecar.write_bytes(invented_vdf())
        if len(list(self.root.glob('*[vV][dD][fF]'))) > 1:
            with self.assertRaises(SaveError):
                owner.read_owner(self.save)
        # Case-insensitive Windows storage cannot create both names. Exercise
        # the same fail-closed inventory branch independently on every platform.
        with patch.object(Path, 'iterdir', return_value=iter((self.sidecar, upper))), self.assertRaises(SaveError):
            owner.read_owner(self.save)

    def test_mutated_missing_and_forged_original_context_reject(self):
        context = owner.read_owner(self.save)
        self.sidecar.write_bytes(invented_vdf(b'4343'))
        with self.assertRaises(SaveError):
            owner.validate_owner(context)
        self.sidecar.unlink()
        with self.assertRaises(SaveError):
            owner.validate_owner(context)
        self.sidecar.write_bytes(invented_vdf())
        for forged in (None, {}, replace(context, raw=bytearray(context.raw)),
                       replace(context, source='plain-string'),
                       replace(context, source=context.source.with_name('remotecache.vdf'))):
            with self.assertRaises(SaveError):
                owner.validate_owner(forged)

    def test_exact_destination_bundle_matching_no_owner_conversion_or_writes(self):
        context = owner.read_owner(self.save)
        destination = self.root / 'edited' / 'new.bin'
        destination.parent.mkdir()
        with self.assertRaises(SaveError):
            owner.require_matching_owner(context, destination)
        companion = destination.parent / context.basename
        companion.write_bytes(invented_vdf(b'4343'))
        with self.assertRaises(SaveError):
            owner.require_matching_owner(context, destination)
        # Same numeric owner with different original bytes still fails binding.
        companion.write_bytes(context.raw.replace(b'\r\n', b'\n'))
        with self.assertRaises(SaveError):
            owner.require_matching_owner(context, destination)
        companion.write_bytes(context.raw)
        matched = owner.require_matching_owner(context, destination)
        self.assertEqual(matched.sha256, context.sha256)
        self.assertFalse(destination.exists())
        self.assertEqual(self.save.read_bytes(), b'copied game bytes')
        self.assertEqual(self.sidecar.read_bytes(), context.raw)

    def test_cloud_paths_and_general_metadata_access_remain_prohibited(self):
        with self.assertRaises(SaveError):
            safe_path(self.sidecar)
        cloud = self.root / 'Steam' / 'userdata' / 'fake' / 'fake' / 'remote'
        cloud.mkdir(parents=True)
        (cloud / owner.OWNER_BASENAME).write_bytes(invented_vdf())
        with self.assertRaises(SaveError):
            owner.read_owner(cloud / 'copy.bin')
        for invalid in (None, [], {}):
            with self.assertRaises(SaveError):
                owner.read_owner(invalid)

    def test_hardlinks_and_nonregular_sidecars_reject(self):
        alias = self.root / 'linked.vdf'
        os.link(self.sidecar, alias)
        with self.assertRaises(SaveError):
            owner.read_owner(self.save)
        alias.unlink()
        self.sidecar.unlink()
        self.sidecar.mkdir()
        with self.assertRaises(SaveError):
            owner.read_owner(self.save)

    def test_linked_and_nonregular_save_bundle_paths_reject(self):
        alias = self.root / 'linked.bin'
        os.link(self.save, alias)
        with self.assertRaises(SaveError):
            owner.read_owner(self.save)
        alias.unlink()
        self.save.unlink()
        self.save.mkdir()
        with self.assertRaises(SaveError):
            owner.read_owner(self.save)

    def test_sidecar_and_parent_symlinks_reject(self):
        target = self.root / 'original.vdf'
        self.sidecar.rename(target)
        try:
            self.sidecar.symlink_to(target)
        except OSError as error:
            self.skipTest(f'Symlink creation is unavailable: {type(error).__name__}.')
        with self.assertRaises(SaveError):
            owner.read_owner(self.save)
        self.sidecar.unlink()
        self.sidecar.write_bytes(invented_vdf())
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(SaveError):
            owner.read_owner(alias / self.save.name)

    def test_metadata_changed_during_bounded_read_rejects(self):
        original = owner.os.fstat
        calls = 0

        def changed_after_read(fd):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.sidecar.write_bytes(invented_vdf(b'4343'))
            return original(fd)

        with patch.object(owner.os, 'fstat', side_effect=changed_after_read), self.assertRaises(SaveError):
            owner.read_owner(self.save)

    def test_same_size_rewrite_with_unchanged_timestamps_rejects(self):
        original = owner.os.fstat
        before = self.sidecar.stat()
        calls = 0

        def stable_stat(info):
            return SimpleNamespace(st_dev=info.st_dev, st_ino=info.st_ino,
                                   st_size=info.st_size, st_mtime_ns=before.st_mtime_ns,
                                   st_mode=info.st_mode, st_nlink=info.st_nlink)

        def changed_after_read(fd):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.sidecar.write_bytes(invented_vdf(b'4343'))
            return stable_stat(original(fd))

        lstat = Path.lstat
        def observed_lstat(path):
            info = lstat(path)
            return stable_stat(info) if path == self.sidecar else info

        with patch.object(owner.os, 'fstat', side_effect=changed_after_read), \
             patch.object(Path, 'lstat', side_effect=observed_lstat, autospec=True), \
             self.assertRaisesRegex(SaveError, 'changed while being read'):
            owner.read_owner(self.save)
        with patch.object(owner.os, 'fstat', side_effect=lambda fd: stable_stat(original(fd))), \
             patch.object(Path, 'lstat', side_effect=observed_lstat, autospec=True):
            self.assertEqual(owner.read_owner(self.save).raw, invented_vdf(b'4343'))

    def test_identical_short_reads_cannot_admit_valid_prefix(self):
        prefix = invented_vdf()
        self.sidecar.write_bytes(prefix + b'foreign trailing bytes')
        with patch.object(owner.os, 'read', return_value=prefix), \
             self.assertRaisesRegex(SaveError, 'changed while being read'):
            owner.read_owner(self.save)

    def test_source_context_change_after_destination_check_rejected_on_recheck(self):
        context = owner.read_owner(self.save)
        directory = self.root / 'bundle'
        directory.mkdir()
        (directory / context.basename).write_bytes(context.raw)
        owner.require_matching_owner(context, directory / 'new.bin')
        self.sidecar.write_bytes(invented_vdf(b'4343'))
        with self.assertRaises(SaveError):
            owner.require_matching_owner(context, directory / 'new.bin')
