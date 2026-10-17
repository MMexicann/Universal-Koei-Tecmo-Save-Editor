"""Read-only diagnostic qualification, integrity, context, races and privacy."""
from dataclasses import FrozenInstanceError
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.game_registry import GAMES
from koei_editor.games.dw3 import save_parser, save_writer
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.nobunaga_ambition_nes import parser as nes
from koei_editor.games.deception4_ps3 import parser as ps3
from koei_editor.shared import save_doctor as doctor
from koei_editor.shared import verified_editor
from tests.test_elixirs_v11 import synthetic_reset_save
from tests.test_nobunaga_ambition_nes import procedural_raw
from tests.test_ps3_new_families import fixture
from tests import test_ps3_expansion as ps3_helpers
from tests import test_save_library as library_helpers
from tests.test_verified_editors import synthetic_raw
from tests.test_fatal_frame2_remake import procedural_raw as fatal_frame_raw


class SaveDoctorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.raw = procedural_raw()
        self.path = self.folder / 'private-player-name.sav'
        self.path.write_bytes(self.raw)

    @staticmethod
    def checks(report):
        return {check.code: check for check in report.checks}

    def test_checksum_native_roundtrip_reference_hash_and_privacy(self):
        digest = hashlib.sha256(self.raw).hexdigest()
        with patch.object(nes, 'serialize', wraps=nes.serialize) as serialize:
            report = doctor.inspect_save(nes.GAME_ID, self.path, expected_sha256=digest.upper())
        self.assertEqual(serialize.call_count, 1)
        self.assertEqual(report.status, 'qualified')
        self.assertTrue(report.success)
        self.assertEqual((report.sha256, report.size_bytes, report.mapped_fields), (digest, len(self.raw), 32))
        for code in ('copy_safety', 'bounded_read', 'expected_sha256', 'compatibility',
                     'native_integrity', 'unchanged_roundtrip', 'source_unchanged'):
            self.assertEqual(self.checks(report)[code].status, 'passed')
        document = report.to_dict()
        self.assertTrue(document['read_only'])
        self.assertEqual(json.loads(report.to_json())['sha256'], digest)
        self.assertIn('byte-for-byte identical', report.to_text())
        for private in (str(self.path), self.path.name, 'Tokugawa', '54321', 'Lord0'):
            self.assertNotIn(private, report.to_json())
            self.assertNotIn(private, report.to_text())
        self.assertFalse({'document', 'raw', 'payload', 'source', 'path', 'owner'} & document.keys())
        self.assertEqual(self.path.read_bytes(), self.raw)
        self.assertEqual(list(self.folder.iterdir()), [self.path])
        with self.assertRaises(FrozenInstanceError):
            report.status = 'failed'

    def test_corruption_truncation_reference_difference_and_wrong_profile_are_distinct(self):
        raw = bytearray(self.raw)
        raw[1] ^= 1
        self.path.write_bytes(raw)
        report = doctor.inspect_save(nes.GAME_ID, self.path)
        self.assertEqual(report.status, 'failed')
        self.assertEqual(self.checks(report)['native_integrity'].status, 'failed')
        self.assertEqual(self.checks(report)['unchanged_roundtrip'].status, 'not_assessed')
        self.assertEqual(self.path.read_bytes(), raw)
        self.path.write_bytes(self.raw[:-1])
        report = doctor.inspect_save(nes.GAME_ID, self.path)
        self.assertEqual(report.status, 'failed')
        self.assertEqual(self.checks(report)['structure'].status, 'failed')
        self.path.write_bytes(self.raw)
        report = doctor.inspect_save(nes.GAME_ID, self.path, expected_sha256='0' * 64)
        self.assertFalse(report.success)
        self.assertEqual(self.checks(report)['expected_sha256'].status, 'failed')
        self.assertEqual(self.checks(report)['unchanged_roundtrip'].status, 'passed')
        with patch.object(nes, 'read_save', side_effect=AssertionError('Wrong parser tried')):
            report = doctor.inspect_save('pokemon_conquest_ds', self.path)
        self.assertEqual(report.status, 'failed')

    def test_every_registered_profile_receives_only_its_explicit_reader(self):
        # Empty generated files exercise registration/import compatibility and
        # rejection paths; they are not valid fixtures or native-load evidence.
        for game in GAMES:
            with self.subTest(game=game.id):
                path = self.folder / ('empty-' + game.id + game.extension)
                path.write_bytes(b'')
                report = doctor.inspect_save(game.id, path)
                self.assertFalse(report.success)
                self.assertEqual(report.game_id, game.id)
                self.assertEqual(self.checks(report)['source_unchanged'].status, 'passed')
                self.assertNotIn('diagnostic_runtime', self.checks(report))

    def test_encrypted_pc_and_dw3_bespoke_actual_serializers(self):
        path = self.folder / 'encrypted.dat'
        path.write_bytes(synthetic_raw('dw8xl'))
        with patch.object(verified_editor, 'serialize', wraps=verified_editor.serialize) as serialize:
            report = doctor.inspect_save('dw8xl', path)
        self.assertTrue(report.success)
        self.assertEqual(serialize.call_count, 1)
        self.assertEqual(self.checks(report)['native_integrity'].status, 'passed')
        document = synthetic_reset_save()
        self.path.write_bytes(document.encrypted)
        with patch.object(save_writer, 'serialize', wraps=save_writer.serialize) as serialize:
            report = doctor.inspect_save('dw3', self.path)
        self.assertTrue(report.success)
        self.assertIsNone(report.mapped_fields)
        self.assertEqual(serialize.call_count, 1)
        self.assertEqual(self.checks(report)['unchanged_roundtrip'].status, 'passed')
        self.assertEqual(self.checks(report)['native_integrity'].status, 'not_assessed')
        self.assertEqual(self.path.read_bytes(), document.encrypted)

    def test_large_registered_fatal_frame_system_save_is_qualified_with_bounded_reads(self):
        raw = fatal_frame_raw()
        self.assertGreater(len(raw), 32 * 1024 * 1024)
        path = self.folder / 'system.bin'
        path.write_bytes(raw)
        reads = []
        original = os.read
        def recorded(descriptor, count):
            reads.append(count)
            return original(descriptor, count)
        with patch.object(doctor.library.os, 'read', side_effect=recorded):
            report = doctor.inspect_save('fatal_frame2_remake', path)
        self.assertTrue(report.success, report.to_text())
        self.assertEqual(report.size_bytes, len(raw))
        self.assertEqual(report.sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(self.checks(report)['unchanged_roundtrip'].status, 'passed')
        self.assertEqual(self.checks(report)['source_unchanged'].status, 'passed')
        self.assertTrue(reads)
        self.assertLessEqual(max(reads), 65536)
        self.assertEqual(path.read_bytes(), raw)
        report = doctor.inspect_save('fatal_frame2_remake', path, max_file_bytes=32 * 1024 * 1024)
        self.assertEqual(report.status, 'oversized')

    def ps3_copy(self):
        path = self.folder / 'DATA.BIN'
        path.write_bytes(fixture(ps3))
        metadata = path.parent / 'PARAM.SFO'
        metadata.write_bytes(ps3_helpers.PS3ContextTests.metadata('NPUB31442-GAMEDATA-10'))
        return path, metadata

    def test_original_context_required_external_integrity_and_context_races(self):
        path, metadata = self.ps3_copy()
        report = doctor.inspect_save(ps3.GAME_ID, path)
        self.assertTrue(report.success)
        self.assertEqual(self.checks(report)['native_integrity'].status, 'not_assessed')
        metadata.unlink()
        report = doctor.inspect_save(ps3.GAME_ID, path)
        self.assertFalse(report.success)
        self.assertEqual(self.checks(report)['original_context'].status, 'failed')
        path, metadata = self.ps3_copy()
        original = ps3.serialize
        def changed_context(*args, **kwargs):
            raw = original(*args, **kwargs)
            metadata.write_bytes(ps3_helpers.PS3ContextTests.metadata('NPUB31442-GAMEDATA-11'))
            return raw
        with patch.object(ps3, 'serialize', side_effect=changed_context):
            report = doctor.inspect_save(ps3.GAME_ID, path)
        self.assertEqual(report.status, 'changed')
        self.assertEqual(self.checks(report)['source_unchanged'].status, 'failed')
        self.assertNotIn('NPUB31442-GAMEDATA-11', report.to_json())

    def test_no_checksum_and_unknown_coverage_are_never_reported_verified(self):
        for kind in ('none', 'external', None):
            with self.subTest(kind=kind), patch.object(nes, 'INTEGRITY_KIND', kind):
                report = doctor.inspect_save(nes.GAME_ID, self.path)
            self.assertTrue(report.success)
            self.assertEqual(self.checks(report)['native_integrity'].status, 'not_assessed')

    def test_opaque_context_digest_is_rechecked_independently_of_context_stat_guard(self):
        path, metadata = self.ps3_copy()
        original = ps3.serialize
        def changed_context(*args, **kwargs):
            raw = original(*args, **kwargs)
            metadata.write_bytes(ps3_helpers.PS3ContextTests.metadata('NPUB31442-GAMEDATA-11'))
            return raw
        # This models a context convention unknown to the shared stat guard:
        # the exact native reader still retains and rechecks its opaque digest.
        with patch.object(doctor.library, '_context_guard', return_value=()), \
                patch.object(ps3, 'serialize', side_effect=changed_context):
            report = doctor.inspect_save(ps3.GAME_ID, path)
        self.assertEqual(report.status, 'changed')
        self.assertEqual(self.checks(report)['source_unchanged'].status, 'failed')

    def test_nonidentical_native_roundtrip_fails_without_repair(self):
        with patch.object(nes, 'serialize', return_value=self.raw[:-1]):
            report = doctor.inspect_save(nes.GAME_ID, self.path)
        self.assertEqual(report.status, 'failed')
        self.assertEqual(self.checks(report)['unchanged_roundtrip'].status, 'failed')
        self.assertEqual(self.path.read_bytes(), self.raw)
        self.assertEqual(list(self.folder.iterdir()), [self.path])

    def test_source_mutation_after_each_native_readback_is_detected(self):
        original = nes.read_save
        for mutation_call in (1, 2):
            self.path.write_bytes(self.raw)
            calls = []
            def changed_source(*args, **kwargs):
                document = original(*args, **kwargs)
                calls.append(True)
                if len(calls) == mutation_call:
                    self.path.write_bytes(self.raw[:-1])
                return document
            with self.subTest(call=mutation_call), patch.object(nes, 'read_save', side_effect=changed_source):
                report = doctor.inspect_save(nes.GAME_ID, self.path)
            self.assertEqual(report.status, 'changed')
            self.assertEqual(self.checks(report)['source_unchanged'].status, 'failed')

    def test_path_and_handle_ctime_differ_without_false_source_change(self):
        original = os.fstat
        def different_clock(descriptor):
            info = original(descriptor)
            return library_helpers.SaveLibraryTests.stat_values(info, st_ctime_ns=info.st_ctime_ns + 1000000)
        with patch.object(doctor.library.os, 'fstat', side_effect=different_clock):
            self.assertTrue(doctor.inspect_save(nes.GAME_ID, self.path).success)

    def test_runtime_failures_and_backend_exception_details_do_not_claim_corruption(self):
        private = 'private-owner-name /private/account/123456789 PARAM.SFO content'
        for error in (SaveError('Checksum mismatch ' + private), RuntimeError(private), OSError(private)):
            with self.subTest(error=type(error)), patch.object(nes, 'read_save', side_effect=error):
                report = doctor.inspect_save(nes.GAME_ID, self.path)
            self.assertFalse(report.success)
            self.assertNotIn(private, report.to_text())
            self.assertNotIn('123456789', report.to_json())
        with patch.object(nes, 'read_save', side_effect=RuntimeError(private)):
            report = doctor.inspect_save(nes.GAME_ID, self.path)
        self.assertIn('does not establish save corruption', self.checks(report)['diagnostic_runtime'].message)

    def test_dw3_compatibility_caveats_are_reported_without_saved_values(self):
        document = synthetic_reset_save()
        self.path.write_bytes(document.encrypted)
        original = save_parser.read_save
        def with_caveat(*args):
            doc = original(*args)
            doc.compatibility_warnings.append('Private saved name: SecretPlayer with unusual value 123456789')
            return doc
        with patch.object(save_parser, 'read_save', side_effect=with_caveat):
            report = doctor.inspect_save('dw3', self.path)
        self.assertEqual(report.status, 'warning')
        self.assertTrue(report.success)
        self.assertEqual(self.checks(report)['compatibility_notes'].status, 'warning')
        self.assertNotIn('SecretPlayer', report.to_json())

    def test_limits_options_and_extension_reject_before_native_parser(self):
        with patch.object(nes, 'read_save', side_effect=AssertionError('Native parser invoked')):
            report = doctor.inspect_save(nes.GAME_ID, self.path, max_file_bytes=1)
            self.assertEqual(report.status, 'oversized')
            wrong = self.folder / 'wrong.dat'
            wrong.write_bytes(self.raw)
            report = doctor.inspect_save(nes.GAME_ID, wrong)
            self.assertEqual(self.checks(report)['compatibility'].status, 'failed')
            for limit in (0, True, 1.5, doctor.MAX_FILE_BYTES + 1):
                with self.subTest(limit=limit), self.assertRaises(SaveError):
                    doctor.inspect_save(nes.GAME_ID, self.path, max_file_bytes=limit)
            for digest in ('', '0' * 63, 'g' * 64, True, b'0' * 64):
                with self.subTest(digest=digest), self.assertRaises(SaveError):
                    doctor.inspect_save(nes.GAME_ID, self.path, expected_sha256=digest)
        with self.assertRaises(SaveError):
            doctor.inspect_save('not-a-game', self.path)

    def test_read_sizes_and_live_cloud_link_hardlink_and_context_guards(self):
        reads = []
        original = os.read
        def recorded(descriptor, count):
            reads.append(count)
            return original(descriptor, count)
        with patch.object(doctor.library.os, 'read', side_effect=recorded):
            self.assertTrue(doctor.inspect_save(nes.GAME_ID, self.path).success)
        self.assertTrue(reads)
        self.assertLessEqual(max(reads), 65536)
        cloud = self.folder / 'Steam/userdata/account/game/remote/save.sav'
        cloud.parent.mkdir(parents=True)
        cloud.write_bytes(self.raw)
        with patch.object(nes, 'read_save', side_effect=AssertionError('Unsafe path parsed')):
            self.assertEqual(doctor.inspect_save(nes.GAME_ID, cloud).status, 'unsafe')
        hardlink = self.folder / 'alias.sav'
        try:
            os.link(self.path, hardlink)
        except OSError:
            pass
        else:
            self.assertEqual(doctor.inspect_save(nes.GAME_ID, hardlink).status, 'unsafe')
            hardlink.unlink()
        linked = self.folder / 'linked.sav'
        try:
            linked.symlink_to(self.path)
        except OSError:
            return
        self.assertEqual(doctor.inspect_save(nes.GAME_ID, linked).status, 'unsafe')
        (self.folder / 'PARAM.SFO').symlink_to(self.path)
        self.assertEqual(doctor.inspect_save(nes.GAME_ID, self.path).status, 'unsafe')

    def test_unreadable_and_new_atomic_private_reports(self):
        missing = doctor.inspect_save(nes.GAME_ID, self.folder / 'missing.sav')
        self.assertEqual(missing.status, 'unreadable')
        self.assertIsNone(missing.sha256)
        report = doctor.inspect_save(nes.GAME_ID, self.path)
        for suffix in ('.json', '.txt'):
            destination = self.folder / ('report' + suffix)
            # Windows temp folders may use an 8.3 user-directory alias while
            # safe_path returns its canonical long path. Verify file identity.
            self.assertTrue(doctor.export_report(report, destination).samefile(destination))
            expected = report.to_json() if suffix == '.json' else report.to_text()
            self.assertEqual(destination.read_text(encoding='utf-8'), expected)
            with self.assertRaises(FileExistsError):
                doctor.export_report(report, destination)
        for destination in (self.folder / 'output.sav', self.folder / 'Steam/userdata/report.json'):
            with self.assertRaises(SaveError):
                doctor.export_report(report, destination)
        self.assertEqual(self.path.read_bytes(), self.raw)


if __name__ == '__main__':
    unittest.main()
