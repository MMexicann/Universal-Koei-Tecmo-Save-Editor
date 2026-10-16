"""Bounded copied-save scans, native context, aliases, races and privacy."""
from dataclasses import fields, replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from koei_editor.games.deception4_ps3 import parser
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared import save_library as library
from tests import test_ps3_expansion as ps3_helpers
from tests.test_ps3_new_families import fixture


class SaveLibraryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.raw = fixture(parser)

    def copy(self, relative='one/DATA.BIN', *, context=True, raw=None, slot='10'):
        path = self.folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.raw if raw is None else raw)
        if context:
            (path.parent / 'PARAM.SFO').write_bytes(ps3_helpers.PS3ContextTests.metadata('NPUB31442-GAMEDATA-' + slot))
        return path

    def scan(self, **kwargs):
        return library.scan(parser.GAME_ID, self.folder, recursive=True, **kwargs)

    def test_exact_profile_context_qualification_and_file_byte_duplicates(self):
        first = self.copy('one/DATA.BIN')
        second = self.copy('two/DATA.BIN', slot='11')
        missing = self.copy('missing/DATA.BIN', context=False)
        corrupt = self.copy('bad/DATA.BIN', raw=self.raw[:-1])
        self.copy('other/ignored.dat')
        result = self.scan()
        entries = {entry.relative_path: entry for entry in result.entries}
        self.assertEqual(len(entries), 4)
        self.assertEqual(result.qualified_count, 2)
        self.assertEqual(entries['missing/DATA.BIN'].status, 'rejected')
        self.assertEqual(entries['bad/DATA.BIN'].status, 'rejected')
        self.assertEqual(entries['one/DATA.BIN'].duplicate_group, entries['two/DATA.BIN'].duplicate_group)
        self.assertNotEqual(entries['one/DATA.BIN'].duplicate_group, 0)
        self.assertNotEqual(entries['one/DATA.BIN'].snapshot_digest, entries['two/DATA.BIN'].snapshot_digest)
        self.assertEqual(entries['missing/DATA.BIN'].duplicate_group, 0)
        document = library.requalify(result, entries['one/DATA.BIN'])
        self.assertEqual(document.raw, self.raw)
        self.assertEqual(entries['one/DATA.BIN'].sha256, hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(entries['one/DATA.BIN'].mapped_fields, 1)
        for path in (first, second, missing):
            self.assertEqual(path.read_bytes(), self.raw)
        self.assertEqual(corrupt.read_bytes(), self.raw[:-1])
        self.assertFalse(any('Backup' in path.name for path in self.folder.rglob('*')))
        # Inventory objects contain only bounded metadata, never raw/payload.
        self.assertFalse({'raw', 'payload', 'document', 'owner', 'context'} & {field.name for field in fields(library.LibraryEntry)})

    def test_wrong_selected_game_and_unsupported_bespoke_profile_never_fall_back(self):
        self.copy()
        for game_id in ('dw3', 'not-a-game', 'atelier_escha_logy_dx'):
            with self.assertRaises(SaveError):
                library.scan(game_id, self.folder)
        with patch.object(parser, 'read_save', side_effect=AssertionError('A different profile was probed')):
            result = library.scan('dw6_ps3', self.folder, recursive=True)
        self.assertEqual([entry.status for entry in result.entries], ['rejected'])

    def test_explicit_recursion_depth_and_file_entry_byte_limits(self):
        self.copy('root.bin')
        self.copy('a/one.bin')
        self.copy('a/b/two.bin')
        self.copy('a/b/c/three.bin')
        self.copy('a/b/c/d/four.bin')
        flat = library.scan(parser.GAME_ID, self.folder)
        self.assertEqual([entry.relative_path for entry in flat.entries], ['root.bin'])
        full = self.scan()
        self.assertEqual(len(full.entries), 4)
        self.assertGreater(full.excluded_directories, 0)
        limited = self.scan(limits=library.ScanLimits(max_depth=1))
        self.assertEqual(len(limited.entries), 2)
        result = self.scan(limits=library.ScanLimits(max_files=2))
        self.assertEqual((len(result.entries), result.stop_reason), (2, 'file_limit'))
        result = self.scan(limits=library.ScanLimits(max_entries=2))
        self.assertEqual((result.visited_entries, result.stop_reason), (2, 'entry_limit'))
        result = self.scan(limits=library.ScanLimits(max_total_bytes=len(self.raw)))
        self.assertEqual((result.admitted_bytes, result.stop_reason), (len(self.raw), 'byte_limit'))
        self.assertEqual(len(result.entries), 1)

    def test_oversize_rejected_without_backend_read_and_limits_cannot_be_raised(self):
        self.copy('large.bin')
        with patch.object(parser, 'read_save', side_effect=AssertionError('Oversized bytes reached parser')):
            result = self.scan(limits=library.ScanLimits(max_file_bytes=64))
        self.assertEqual((result.entries[0].status, result.admitted_bytes), ('oversized', 0))
        for limits in (library.ScanLimits(max_files=501), library.ScanLimits(max_entries=True),
                       library.ScanLimits(max_depth=4), library.ScanLimits(max_total_bytes=0),
                       library.ScanLimits(max_file_bytes=32 * 1024 * 1024 + 1), {}):
            with self.assertRaises(SaveError):
                self.scan(limits=limits)
        with self.assertRaises(SaveError):
            library.scan(parser.GAME_ID, self.folder, recursive=1)

    def test_source_and_valid_original_context_changes_require_rescan(self):
        path = self.copy()
        result = self.scan()
        entry = result.entries[0]
        path.write_bytes(parser.serialize(parser.decode(self.raw), {'warl': 42}))
        with self.assertRaises(SaveError):
            library.requalify(result, entry)
        path.write_bytes(self.raw)
        result = self.scan()
        metadata = path.parent / 'PARAM.SFO'
        metadata.write_bytes(ps3_helpers.PS3ContextTests.metadata('NPUB31442-GAMEDATA-11'))
        with self.assertRaisesRegex(SaveError, 'context changed'):
            library.requalify(result, result.entries[0])
        metadata.unlink()
        with self.assertRaises(SaveError):
            library.requalify(result, result.entries[0])

    def test_concurrent_source_mutation_never_receives_qualified_status(self):
        path = self.copy()
        original = parser.read_save
        def altered(*args, **kwargs):
            document = original(*args, **kwargs)
            path.write_bytes(self.raw[:-1])
            return document
        with patch.object(parser, 'read_save', side_effect=altered):
            result = self.scan()
        self.assertEqual([entry.status for entry in result.entries], ['changed'])
        self.assertEqual(path.read_bytes(), self.raw[:-1])

    def test_root_replacement_with_unchanged_file_inodes_requires_rescan(self):
        path = self.copy()
        # Keep replacement operations inside the TemporaryDirectory so both
        # old and new folders are cleaned up on every supported host.
        root = self.folder / 'library'
        root.mkdir()
        path.parent.rename(root / 'one')
        result = library.scan(parser.GAME_ID, root, recursive=True)
        entry = result.entries[0]
        old_root = self.folder / 'old-library'
        original = parser.read_save
        replaced = []
        def replace_folder(*args, **kwargs):
            document = original(*args, **kwargs)
            root.rename(old_root)
            root.mkdir()
            (old_root / 'one').rename(root / 'one')
            replaced.append(True)
            return document
        with patch.object(parser, 'read_save', side_effect=replace_folder):
            with self.assertRaisesRegex(SaveError, 'folder changed identity'):
                library.requalify(result, entry)
        self.assertEqual(replaced, [True])
        self.assertEqual((root / 'one' / 'DATA.BIN').read_bytes(), self.raw)
        self.assertEqual((root / 'one' / 'DATA.BIN').stat().st_ino, entry.identity[1])

    def test_cancelled_scan_never_returns_partial_file_qualification(self):
        path = self.copy()
        cancel = threading.Event()
        cancel.set()
        result = self.scan(cancel=cancel)
        self.assertEqual((result.entries, result.stop_reason), ((), 'cancelled'))
        cancel.clear()
        original = parser.read_save
        def stopped(*args, **kwargs):
            document = original(*args, **kwargs)
            cancel.set()
            return document
        with patch.object(parser, 'read_save', side_effect=stopped):
            result = self.scan(cancel=cancel)
        self.assertEqual((result.entries, result.stop_reason), ((), 'cancelled'))
        self.assertEqual(path.read_bytes(), self.raw)

    def test_stream_reads_are_bounded_and_not_cached_as_inventory_payloads(self):
        self.copy('one.bin')
        requested = []
        original = os.read
        def recorded(descriptor, count):
            requested.append(count)
            return original(descriptor, count)
        with patch.object(library.os, 'read', side_effect=recorded):
            result = self.scan()
        self.assertTrue(requested)
        self.assertLessEqual(max(requested), 65536)
        self.assertEqual(result.admitted_bytes, len(self.raw))
        self.assertEqual(result.entries[0].status, 'qualified')
        with patch.object(parser, 'read_save', wraps=parser.read_save) as read:
            library.requalify(result, result.entries[0])
        self.assertEqual(read.call_count, 1)

    @staticmethod
    def stat_values(info, **overrides):
        values = {name: getattr(info, name) for name in dir(info) if name.startswith('st_')}
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_path_and_handle_ctime_can_differ_without_rejecting_untouched_copies(self):
        self.copy('ordinary.bin')
        original = os.fstat
        def different_clock(descriptor):
            info = original(descriptor)
            # CPython on Windows uses birth time for path st_ctime but native
            # change time for handle st_ctime. Deliberately make them unequal
            # on every host so this compatibility regression stays active.
            return self.stat_values(info, st_ctime_ns=info.st_ctime_ns + 123456789)
        with patch.object(library.os, 'fstat', side_effect=different_clock), \
                patch.object(parser, 'read_save', wraps=parser.read_save) as read:
            result = self.scan()
            self.assertEqual(result.qualified_count, 1)
            document = library.requalify(result, result.entries[0])
        self.assertEqual(read.call_count, 2)
        self.assertEqual(document.raw, self.raw)

    def test_same_api_handle_and_path_timestamp_changes_still_reject_reads(self):
        path = self.copy('time-change.bin')
        _, info = library._checked_path(path)
        expected = library._identity(info)
        original_read, original_fstat, original_lstat = os.read, os.fstat, Path.lstat
        for changed_api in ('handle', 'path'):
            with self.subTest(changed_api=changed_api):
                reads = []
                def read(descriptor, count):
                    data = original_read(descriptor, count)
                    reads.append(count)
                    return data
                def fstat(descriptor):
                    value = original_fstat(descriptor)
                    delta = 123456789 + (1 if reads and changed_api == 'handle' else 0)
                    return self.stat_values(value, st_ctime_ns=value.st_ctime_ns + delta)
                def lstat(candidate, *args, **kwargs):
                    value = original_lstat(candidate, *args, **kwargs)
                    if reads and changed_api == 'path' and candidate.name == path.name:
                        return self.stat_values(value, st_ctime_ns=value.st_ctime_ns + 1)
                    return value
                with patch.object(library.os, 'read', side_effect=read), \
                        patch.object(library.os, 'fstat', side_effect=fstat), \
                        patch.object(Path, 'lstat', lstat):
                    with self.assertRaisesRegex(SaveError, 'changed during'):
                        library._capture(path, expected, library.ScanLimits().max_file_bytes, None)
                self.assertTrue(reads, 'The timestamp must change after bounded reading begins.')
        self.assertEqual(path.read_bytes(), self.raw)

    def test_cross_api_handle_binding_rejects_other_files_before_reading(self):
        path = self.copy('binding.bin')
        _, info = library._checked_path(path)
        expected = library._identity(info)
        original = os.fstat
        for changed_attribute in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns'):
            with self.subTest(changed_attribute=changed_attribute):
                def different_file(descriptor):
                    value = original(descriptor)
                    return self.stat_values(value,
                        **{changed_attribute: getattr(value, changed_attribute) + 1})
                with patch.object(library.os, 'fstat', side_effect=different_file), \
                        patch.object(library.os, 'read') as read:
                    with self.assertRaisesRegex(SaveError, 'changed before'):
                        library._capture(path, expected, library.ScanLimits().max_file_bytes, None)
                read.assert_not_called()

    def test_same_bytes_path_replacement_during_read_cannot_pass_as_original(self):
        path = self.copy('replacement.bin')
        _, info = library._checked_path(path)
        expected = library._identity(info)
        original_read, original_lstat = os.read, Path.lstat
        reads = []
        def read(descriptor, count):
            data = original_read(descriptor, count)
            reads.append(count)
            return data
        def replacement(candidate, *args, **kwargs):
            value = original_lstat(candidate, *args, **kwargs)
            if reads and candidate.name == path.name:
                # Model a different inode with identical bytes, size and times
                # without depending on Windows delete-sharing privileges.
                return self.stat_values(value, st_ino=value.st_ino + 1)
            return value
        with patch.object(library.os, 'read', side_effect=read), \
                patch.object(Path, 'lstat', replacement):
            with self.assertRaisesRegex(SaveError, 'changed during'):
                library._capture(path, expected, library.ScanLimits().max_file_bytes, None)
        self.assertTrue(reads)
        self.assertEqual(path.read_bytes(), self.raw)

    def test_live_cloud_symlink_hardlink_and_directory_aliases_are_never_opened(self):
        path = self.copy()
        for root in ('Steam/userdata/123/456/remote', 'KoeiTecmo/Dynasty Warriors Origins/Savedata'):
            directory = self.folder / root
            directory.mkdir(parents=True)
            with self.assertRaises(SaveError):
                library.scan(parser.GAME_ID, directory)
        linked = self.folder / 'alias.bin'
        directory_alias = self.folder / 'linked-folder'
        try:
            linked.symlink_to(path)
            directory_alias.symlink_to(path.parent, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('This host cannot create symlinks')
        with patch.object(parser, 'read_save', wraps=parser.read_save) as read:
            result = self.scan()
        entries = {entry.relative_path: entry for entry in result.entries}
        self.assertEqual(entries['alias.bin'].status, 'unsafe')
        self.assertNotIn('linked-folder/DATA.BIN', entries)
        self.assertEqual(read.call_count, 1)
        with self.assertRaises(SaveError):
            library.scan(parser.GAME_ID, directory_alias)
        linked.unlink()
        directory_alias.unlink()
        hardlink = self.folder / 'hardlink.bin'
        try:
            os.link(path, hardlink)
        except OSError:
            self.skipTest('This host cannot create hardlinks')
        with patch.object(parser, 'read_save', side_effect=AssertionError('Aliased file reached parser')):
            result = self.scan()
        self.assertTrue(all(entry.status == 'unsafe' for entry in result.entries))

    def test_linked_or_aliased_original_context_is_rejected_before_parser_read(self):
        path = self.copy()
        metadata = path.parent / 'PARAM.SFO'
        original = metadata.read_bytes()
        metadata.unlink()
        other = self.folder / 'private-original.sfo'
        other.write_bytes(original)
        try:
            metadata.symlink_to(other)
        except (OSError, NotImplementedError):
            self.skipTest('This host cannot create symlinks')
        with patch.object(parser, 'read_save', side_effect=AssertionError('Linked context reached parser')):
            result = self.scan()
        self.assertEqual(result.entries[0].status, 'rejected')
        metadata.unlink()
        try:
            os.link(other, metadata)
        except OSError:
            self.skipTest('This host cannot create hardlinks')
        with patch.object(parser, 'read_save', side_effect=AssertionError('Aliased context reached parser')):
            result = self.scan()
        self.assertEqual(result.entries[0].status, 'rejected')
        self.assertEqual(other.read_bytes(), original)

    def test_diagnostics_are_path_owner_context_and_file_hash_free(self):
        self.copy('personal-player-name/DATA.BIN')
        self.copy('other/DATA.BIN')
        result = self.scan()
        report = library.report(result)
        self.assertEqual(report['statuses']['qualified'], 2)
        self.assertEqual(report['identical_gameplay_file_groups'], 1)
        self.assertEqual(report['files_in_identical_gameplay_groups'], 2)
        self.assertTrue(report['historical_scan'])
        text = json.dumps(report)
        for private in (str(self.folder), 'personal-player-name', 'DATA.BIN', 'NPUB31442', 'PARAM.SFO',
                        result.entries[0].sha256, result.entries[0].snapshot_digest):
            self.assertNotIn(private, text)

    def test_unqualified_forged_escaped_and_wrong_profile_results_do_not_open(self):
        self.copy()
        result = self.scan()
        entry = result.entries[0]
        with self.assertRaises(SaveError):
            library.requalify(result, replace(entry, status='rejected'))
        for relative in ('../escape.bin', '/absolute.bin', 'one\\DATA.BIN', 'C:/escape.bin', 'one/./DATA.BIN'):
            forged = replace(entry, relative_path=relative)
            with self.assertRaises(SaveError):
                library.requalify(replace(result, entries=(forged,)), forged)
        for forged in (replace(result, entries=[]), replace(result, game_id='dw3'),
                       replace(result, admitted_bytes=True), replace(result, stop_reason='imaginary'),
                       replace(result, entries=(replace(entry, mapped_fields=True),))):
            with self.assertRaises(SaveError):
                library.report(forged)

    def test_encrypted_pc_owner_dependent_and_psu_profiles_use_normal_bound_readers(self):
        from tests.test_verified_editors import synthetic_raw
        from tests.test_project_zero_ps2 import fixture as psu_fixture
        from tests.test_abyss_pc import procedural as abyss_copy
        pc = self.folder / 'pc'
        pc.mkdir()
        (pc / 'copy.dat').write_bytes(synthetic_raw('dw8xl'))
        result = library.scan('dw8xl', pc)
        self.assertEqual(result.qualified_count, 1)
        self.assertEqual(library.requalify(result, result.entries[0]).raw, (pc / 'copy.dat').read_bytes())
        ps2 = self.folder / 'ps2'
        ps2.mkdir()
        (ps2 / 'copy.psu').write_bytes(psu_fixture())
        result = library.scan('project_zero_ps2', ps2)
        self.assertEqual(result.qualified_count, 1)
        self.assertGreater(result.entries[0].mapped_fields, 0)
        self.assertEqual(library.requalify(result, result.entries[0]).raw, (ps2 / 'copy.psu').read_bytes())
        owner = self.folder / 'owner'
        source = abyss_copy(owner)
        result = library.scan('abyss_pc', owner)
        self.assertEqual(result.qualified_count, 1)
        self.assertEqual(library.requalify(result, result.entries[0]).raw, source.read_bytes())
        text = json.dumps(library.report(result))
        for private in ('accountid', '12345', 'owner_sha256', 'steam_autocloud.vdf'):
            self.assertNotIn(private, text)
        (owner / 'steam_autocloud.vdf').write_bytes(b'"steam_autocloud.vdf" { "accountid" "98765" }')
        with self.assertRaises(SaveError):
            library.requalify(result, result.entries[0])

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'This host does not support FIFO files')
    def test_special_files_are_not_opened_or_hashed(self):
        special = self.folder / 'pipe.bin'
        os.mkfifo(special)
        with patch.object(parser, 'read_save', side_effect=AssertionError('Special file reached parser')):
            result = self.scan()
        self.assertEqual(result.entries[0].status, 'unsafe')
        self.assertEqual(result.admitted_bytes, 0)

    def test_extensionless_profile_keeps_metadata_and_foreign_files_unqualified(self):
        from koei_editor.games.ar_tonelico_qoga_ps3 import parser as qoga
        path = self.folder / 'USR-DATA'
        path.write_bytes(fixture(qoga))
        (self.folder / 'PARAM.SFO').write_bytes(ps3_helpers.PS3ContextTests.metadata('BLUS30639-LIST-08'))
        (self.folder / 'foreign').write_bytes(b'not a game save')
        result = library.scan(qoga.GAME_ID, self.folder)
        self.assertEqual(len(result.entries), 2)
        self.assertEqual({entry.relative_path: entry.status for entry in result.entries},
                         {'USR-DATA': 'qualified', 'foreign': 'rejected'})
        self.assertEqual(library.requalify(result, next(entry for entry in result.entries if entry.status == 'qualified')).raw,
                         path.read_bytes())
