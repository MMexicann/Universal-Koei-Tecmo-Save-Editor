"""Native rejection evidence, privacy, no-op checking and immutable copies."""
from dataclasses import fields, replace
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import threading
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw3.save_codec import encrypt
from koei_editor.games.dw3.save_parser import ARRAY_LAYOUTS
from koei_editor.games.dw7xl import dw7xl_parser as native
from koei_editor.shared import save_doctor as doctor
from koei_editor.shared import save_library as library
from tests.test_dw7xl_format import synthetic_raw, reference_encode
from tests.test_wo3u_ps3 import fixture as ps3_fixture, metadata


def tagged_fixture(engine=(5, 6, 1)):
    """Procedural empty tagged arrays, not a genuine/playable game save."""
    def string(value):
        raw = value.encode() + b'\0'
        return struct.pack('<i', len(raw)) + raw
    def typename(name, *children):
        return string(name) + struct.pack('<i', len(children)) + b''.join(children)
    payload = (b'GVAS' + struct.pack('<iiiHHHI', 3, 522, 1017, *engine, 0)
               + string('procedural') + struct.pack('<ii', 3, 0)
               + string('/Script/Refine.GameStatusSaveGame') + b'\0')
    for name, structure in ARRAY_LAYOUTS.items():
        inner = (typename('StructProperty', typename(structure, typename('/Script/Refine')))
                 if structure else typename('BoolProperty'))
        payload += string(name) + typename('ArrayProperty', inner) + struct.pack('<iB', 4, 0) + bytes(4)
    payload += string('None') + bytes(4)
    plain = struct.pack('>I', len(payload)) + payload
    return encrypt(plain + bytes((-len(plain)) % 16))


class SaveDoctorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = synthetic_raw()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name).resolve()
        self.source = self.folder / 'private-player-copy.dat'
        self.source.write_bytes(self.raw)

    def diagnose(self, **kwargs):
        return doctor.diagnose('dw7xl', self.source, **kwargs)

    @staticmethod
    def codes(result):
        return {finding.code for finding in result.findings}

    def test_native_qualification_roundtrip_freshness_no_writes_or_backup(self):
        with patch.object(native, 'backup', side_effect=AssertionError('Read-only doctor created a backup')):
            result = self.diagnose()
            self.assertTrue(result.qualified)
            self.assertEqual(result.status, 'qualified')
            self.assertEqual(doctor.requalify(result), self.source)
        self.assertTrue({'native.accepted', 'roundtrip.exact', 'source.fixed', 'context.fixed'} <= self.codes(result))
        self.assertGreater(result.mapped_fields, 0)
        self.assertIn('integrity.unreported', self.codes(result))
        self.assertIn('revision.unreported', self.codes(result))
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertEqual(list(self.folder.iterdir()), [self.source])
        self.assertFalse({'raw', 'payload', 'document', 'account'} & {item.name for item in fields(result)})

    def test_actual_checksum_rejection_never_attempts_roundtrip_or_repairs(self):
        self.source.write_bytes(bytes([self.raw[0] ^ 1]) + self.raw[1:])
        with patch.object(native, 'serialize', side_effect=AssertionError('Rejected file reached serializer')):
            result = self.diagnose()
        self.assertFalse(result.qualified)
        self.assertIn('native.checksum_rejected', self.codes(result))
        self.assertNotIn('roundtrip.exact', self.codes(result))
        self.assertNotIn('integrity.unreported', self.codes(result))
        self.assertEqual(self.source.read_bytes(), bytes([self.raw[0] ^ 1]) + self.raw[1:])

    def test_valid_checksum_foreign_marker_is_identity_or_revision_not_corruption_proof(self):
        document = native.decode(self.raw)
        self.source.write_bytes(reference_encode(b'NOPE' + document.payload[4:], document.seed))
        result = self.diagnose()
        self.assertFalse(result.qualified)
        self.assertIn('native.identity_revision_rejected', self.codes(result))
        self.assertNotIn('native.checksum_rejected', self.codes(result))

    def test_truncation_empty_and_foreign_profile_rejected_without_fallback(self):
        self.source.write_bytes(self.raw[:-1])
        self.assertFalse(self.diagnose().qualified)
        self.source.write_bytes(b'')
        self.assertIn('read.empty', self.codes(self.diagnose()))
        self.source.write_bytes(self.raw)
        result = doctor.diagnose('dw8xl', self.source)
        self.assertFalse(result.qualified)
        self.assertNotIn('native.accepted', self.codes(result))

    def test_explicit_extension_and_hard_limits_stop_before_native_read(self):
        wrong = self.folder / 'copy.bin'
        wrong.write_bytes(self.raw)
        with patch.object(native, 'read_save', side_effect=AssertionError('Rejected selection reached parser')):
            self.assertIn('profile.extension_mismatch', self.codes(doctor.diagnose('dw7xl', wrong)))
            self.assertIn('read.oversized', self.codes(self.diagnose(max_file_bytes=32)))
        for limit in (True, 0, -1, doctor.MAX_FILE_BYTES + 1):
            with self.subTest(limit=limit), self.assertRaises(SaveError):
                self.diagnose(max_file_bytes=limit)
        with self.assertRaises(SaveError):
            doctor.diagnose('not-a-game', self.source)

    def test_missing_and_os_errors_are_not_reported_as_corruption(self):
        result = doctor.diagnose('dw7xl', self.folder / 'absent.dat')
        self.assertEqual(result.status, 'unreadable')
        self.assertIn('read.missing', self.codes(result))
        with patch.object(library, '_capture', side_effect=PermissionError('private user path')):
            result = self.diagnose()
        self.assertEqual(result.status, 'unreadable')
        self.assertEqual(next(item.state for item in result.findings if item.code == 'read.unreadable'), 'unknown')
        self.assertNotIn('native.rejected', self.codes(result))

    def test_cloud_and_aliased_files_are_unsafe(self):
        cloud = self.folder / 'Steam/userdata/123/456/remote/copy.dat'
        cloud.parent.mkdir(parents=True)
        cloud.write_bytes(self.raw)
        self.assertEqual(doctor.diagnose('dw7xl', cloud).status, 'unsafe')
        alias = self.folder / 'alias.dat'
        try:
            os.link(self.source, alias)
        except OSError as error:
            self.skipTest(str(error))
        self.assertEqual(self.diagnose().status, 'unsafe')
        self.assertEqual(doctor.diagnose('dw7xl', alias).status, 'unsafe')

    def test_linked_file_and_linked_parent_are_unsafe(self):
        alias = self.folder / 'linked.dat'
        try:
            alias.symlink_to(self.source)
            parent = self.folder / 'linked-parent'
            parent.symlink_to(self.folder, target_is_directory=True)
        except OSError as error:
            self.skipTest(str(error))
        self.assertEqual(doctor.diagnose('dw7xl', alias).status, 'unsafe')
        self.assertEqual(doctor.diagnose('dw7xl', parent / self.source.name).status, 'unsafe')

    def test_native_opaque_error_and_runtime_failure_do_not_leak_private_text(self):
        private = str(self.source) + ' account=player-private-identity'
        for error, expected in ((SaveError(private), 'native.rejected'),
                                (RuntimeError(private), 'native.unavailable'),
                                (TypeError(private), 'native.unavailable')):
            with self.subTest(error=type(error).__name__), patch.object(native, 'read_save', side_effect=error):
                result = self.diagnose()
            text = json.dumps(doctor.report(result))
            self.assertIn(expected, self.codes(result))
            self.assertNotIn(private, text)
            self.assertNotIn(self.source.name, text)
            self.assertNotIn(str(self.folder), text)
            self.assertNotIn('player-private-identity', text)

    def test_combined_error_messages_do_not_isolate_checksum_or_revision(self):
        for message in ('Checksum or signature failed.', 'Checksum failed or missing context.',
                        'Unsupported or damaged header.', 'Unexpected original value: account=private'):
            with self.subTest(message=message), patch.object(native, 'read_save', side_effect=SaveError(message)):
                result = self.diagnose()
            self.assertIn('native.rejected', self.codes(result))
            self.assertNotIn('native.checksum_rejected', self.codes(result))

    def test_source_change_during_native_read_invalidates_result(self):
        read = native.read_save
        def changed(*args, **kwargs):
            document = read(*args, **kwargs)
            self.source.write_bytes(self.raw[:-1])
            return document
        with patch.object(native, 'read_save', side_effect=changed):
            result = self.diagnose()
        self.assertEqual(result.status, 'changed')
        self.assertIn('source.changed', self.codes(result))
        self.assertFalse(result.qualified)

    def test_changed_copy_cannot_be_opened_from_historical_result(self):
        result = self.diagnose()
        self.source.write_bytes(self.raw[:-1])
        with self.assertRaises(SaveError):
            doctor.requalify(result)
        self.assertTrue(doctor.report(result)['historical_snapshot'])

    def test_native_acceptance_with_failed_roundtrip_is_not_openable(self):
        with patch.object(native, 'serialize', return_value=b'wrong'):
            result = self.diagnose()
        self.assertEqual(result.status, 'incomplete')
        self.assertIn('native.accepted', self.codes(result))
        self.assertIn('roundtrip.mismatch', self.codes(result))
        self.assertFalse(result.qualified)
        with self.assertRaises(SaveError):
            doctor.requalify(result)

    def test_cancellation_before_and_during_each_native_read_is_not_qualification(self):
        cancel = threading.Event()
        cancel.set()
        self.assertEqual(self.diagnose(cancel=cancel).status, 'cancelled')
        original = native.read_save
        for cancel_at in (1, 2):
            with self.subTest(cancel_at=cancel_at):
                cancel = threading.Event()
                calls = []
                def read(*args, **kwargs):
                    document = original(*args, **kwargs)
                    calls.append(1)
                    if len(calls) == cancel_at:
                        cancel.set()
                    return document
                with patch.object(native, 'read_save', side_effect=read):
                    result = self.diagnose(cancel=cancel)
                self.assertEqual(result.status, 'cancelled')
                self.assertFalse(result.qualified)
                self.assertIn('operation.cancelled', self.codes(result))

    def test_required_console_context_and_context_changes_are_checked(self):
        source = self.folder / 'APP.BIN'
        source.write_bytes(ps3_fixture())
        result = doctor.diagnose('wo3u_ps3', source)
        self.assertFalse(result.qualified)
        self.assertIn('native.context_rejected', self.codes(result))
        context = self.folder / 'PARAM.SFO'
        context.write_bytes(metadata())
        result = doctor.diagnose('wo3u_ps3', source)
        self.assertTrue(result.qualified)
        context.write_bytes(metadata() + b'private-owner-context')
        with self.assertRaises(SaveError):
            doctor.requalify(result)

    def test_context_change_between_fresh_native_reads_is_not_qualification(self):
        companion = self.folder / 'PARAM.SFO'
        companion.write_bytes(b'original context')
        original = native.read_save
        reads = []
        def read(*args, **kwargs):
            document = original(*args, **kwargs)
            reads.append(1)
            if len(reads) == 2:
                companion.write_bytes(b'changed context')
            return document
        with patch.object(native, 'read_save', side_effect=read):
            result = self.diagnose()
        self.assertEqual(result.status, 'changed')
        self.assertIn('context.changed', self.codes(result))

    def test_tagged_dw3_uses_own_native_parser_and_preserves_compatibility_warning_count(self):
        from koei_editor.shared.adapter_contract import BoundScalarAdapter
        source = self.folder / 'tagged.sav'
        raw = tagged_fixture((5, 6, 2))
        source.write_bytes(raw)
        with patch.object(BoundScalarAdapter, 'read_save', side_effect=AssertionError('Tagged save reached scalar parser')):
            result = doctor.diagnose('dw3', source)
        self.assertEqual(result.status, 'attention')
        self.assertTrue(result.qualified)
        self.assertEqual(result.compatibility_warnings, 1)
        self.assertIsNone(result.mapped_fields)
        self.assertIn('compatibility.warnings', self.codes(result))
        self.assertEqual(source.read_bytes(), raw)

    def test_atomic_privacy_report_export_and_existing_destination_protection(self):
        result = self.diagnose()
        destination = self.folder / 'report.doctor.json'
        self.assertEqual(doctor.export_report(result, destination), destination)
        report = json.loads(destination.read_text())
        self.assertEqual(report, doctor.report(result))
        encoded = destination.read_text()
        for private in (str(self.source), self.source.name, result.sha256, result.snapshot_digest):
            self.assertNotIn(private, encoded)
        self.assertFalse(report['repairs_attempted'])
        self.assertFalse(report['game_load_verified'])
        with self.assertRaises(FileExistsError):
            doctor.export_report(result, destination)
        with self.assertRaises(SaveError):
            doctor.export_report(result, self.folder / 'wrong.json')
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_report_foreign_replacement_is_rejected_and_retained(self):
        result = self.diagnose()
        destination = self.folder / 'report.doctor.json'
        create = doctor.atomic_new
        foreign = b'foreign process bytes'
        def replaced(data, target):
            created = create(data, target)
            created.unlink()
            created.write_bytes(foreign)
            return created
        with patch.object(doctor, 'atomic_new', side_effect=replaced), self.assertRaises(SaveError):
            doctor.export_report(result, destination)
        self.assertEqual(destination.read_bytes(), foreign)

    def test_report_rejects_modified_catalogue_text_and_invalid_qualification(self):
        result = self.diagnose()
        forged = replace(result, findings=(replace(result.findings[0], detail=str(self.source)),))
        with self.assertRaises(SaveError):
            doctor.report(forged)
        forged = replace(result, findings=(doctor.FINDINGS['native.accepted'],))
        with self.assertRaises(SaveError):
            doctor.report(forged)
        with self.assertRaises(SaveError):
            doctor.report(replace(result, created_utc='private/path'))


class OptionalNativeSaveDoctorTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('DW7XL_SAVE_COPY'), 'Private native DW7 XL copy unavailable')
    def test_genuine_pc_copy_is_unchanged_and_no_backup_is_created(self):
        source = Path(os.environ['DW7XL_SAVE_COPY']).resolve()
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        result = doctor.diagnose('dw7xl', source)
        self.assertTrue(result.qualified)
        self.assertEqual(doctor.requalify(result), source)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
