"""Strict title context, source-mapped edits and copied PS3 save workflows."""
from dataclasses import replace
import os
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from koei_editor.games.pw1_ps3 import parser as pw1
from koei_editor.games.pw2_ps3 import parser as pw2
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from tests.scalar_contract import ScalarContractTests


def sfo(directory):
    key = b'SAVEDATA_DIRECTORY\0'
    value = directory.encode('ascii') + b'\0'
    return (struct.pack('<5I', 0x46535000, 0x101, 36, 36 + len(key), 1)
            + struct.pack('<HH3I', 0, 0x204, len(value), len(value), 0) + key + value)


def fixture(backend):
    raw = bytearray((i * 17 + 11) % 256 for i in range(backend.SAVE_SIZE))
    for offset, marker in backend.HEADER_SEGMENTS:
        raw[offset:offset + len(marker)] = marker
    if backend is pw1:
        for i in range(13):
            raw[0x7C + i * 0x80:0x80 + i * 0x80] = (1000 + i * 200).to_bytes(4, 'big')
    else:
        raw[0xA614:0xA61C] = struct.pack('>II', 123456, 654321)
    return bytes(raw)


class ProfileChecks(ScalarContractTests):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.game = SimpleNamespace(extension='.bin')
        self.adapter = BoundScalarAdapter(self.backend.GAME_ID, '.bin', self.backend)
        self.raw = fixture(self.backend)
        self.source = self.folder / 'DATA.BIN'
        self.source.write_bytes(self.raw)
        self.identity = sfo(self.backend.TITLE_IDS[0] + '-00')
        (self.folder / 'PARAM.SFO').write_bytes(self.identity)
        self.document = self.adapter.read_save(self.source)

    def test_all_mapped_values_surgical_and_original_not_modified(self):
        fields = self.adapter.fields_for(self.document)
        self.assertEqual(len(fields), 13 if self.backend is pw1 else 1)
        allowed = set()
        changes = {}
        for field in fields:
            opened = field.value(self.raw)
            changes = self.adapter.stage(self.document, changes, field.id, opened // 2)
            allowed.update(range(field.offset, field.offset + field.size))
        output = self.adapter.serialize(self.document, changes)
        self.assertEqual(self.adapter.changed_payload(self.document, changes), output)
        for field in fields:
            self.assertEqual(field.value(output), changes[field.id])
        self.assertLessEqual({i for i, (a, b) in enumerate(zip(output, self.raw)) if a != b}, allowed)
        self.assertEqual(output[:16], self.raw[:16])
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertEqual(self.adapter.maximums(self.document, changes), changes)
        self.assertEqual(self.adapter.limit_values(self.document, changes, tuple(changes)), {})
        if self.backend is pw2:
            self.assertEqual(output[0xA618:0xA61C], self.raw[0xA618:0xA61C])

    def test_pending_map_bounds_and_exact_typed_opened_values(self):
        field = self.adapter.fields_for(self.document)[0]
        opened = field.value(self.raw)
        for changes in ({field.id: True}, {field.id: -1}, {field.id: opened + 1},
                        {field.id: float(opened)}, {field.id: '0'}, {'unknown': 0}, [], None):
            with self.subTest(changes=changes), self.assertRaises(SaveError):
                self.adapter.serialize(self.document, changes)
        self.assertEqual(self.adapter.stage(self.document, {field.id: 0}, field.id, opened), {})
        self.assertEqual(self.adapter.serialize(self.document, {field.id: opened}), self.raw)
        with self.assertRaises(SaveError):
            self.adapter.stage(self.document, {'unknown': 1}, field.id, opened)
        unusual = bytearray(self.raw)
        unusual[field.offset:field.offset + 4] = b'\xff' * 4
        document = self.backend.decode(bytes(unusual))
        self.assertEqual(self.adapter.stage(document, {}, field.id, 0xFFFFFFFF), {})
        self.assertEqual(self.adapter.serialize(document, {field.id: 0xFFFFFFFF}), bytes(unusual))
        self.assertEqual(self.adapter.maximums(document, {}), {})

    def test_strict_header_export_identity_and_external_integrity_scope(self):
        for i in range(16):
            altered = bytearray(self.raw)
            altered[i] ^= 1
            with self.subTest(offset=i), self.assertRaises(SaveError):
                self.backend.decode(bytes(altered))
        for raw in (self.raw[:-1], self.raw + b'\0', bytearray(self.raw), bytes(len(self.raw))):
            with self.assertRaises(SaveError):
                self.backend.decode(raw)
        for identity in ('BLUS99999-00', self.backend.TITLE_IDS[0] + '-01',
                         self.backend.TITLE_IDS[0] + '-SYSTEM', 'foreign'):
            (self.folder / 'PARAM.SFO').write_bytes(sfo(identity))
            with self.subTest(identity=identity), self.assertRaises(SaveError):
                self.adapter.read_save(self.source)
        (self.folder / 'PARAM.SFO').unlink()
        with self.assertRaises(SaveError):
            self.adapter.read_save(self.source)
        self.assertEqual(self.backend.INTEGRITY_KIND, 'external')
        self.assertFalse(self.backend.FORMAT.game_load_verified)
        altered = bytearray(self.raw)
        altered[-1] ^= 1
        # The source recipe does not qualify an inner corruption detector.
        self.assertEqual(self.backend.serialize(self.backend.decode(bytes(altered)), {}), bytes(altered))

    def test_context_digest_backup_restore_and_write_race(self):
        backup = self.adapter.backup(self.document)
        target = self.folder / 'output.bin'
        edited = self.adapter.save_as(self.document, {}, target)
        self.assertEqual(edited.raw, self.raw)
        # Same title identity with an extra opaque byte is still a different source context.
        (self.folder / 'PARAM.SFO').write_bytes(self.identity + b'\0')
        with self.assertRaises(SaveError):
            self.adapter.save_as(self.document, {}, self.folder / 'changed-context.bin')
        with self.assertRaises(SaveError):
            self.adapter.restore(backup, self.folder / 'wrong-context.bin')
        (self.folder / 'PARAM.SFO').write_bytes(self.identity)
        original = self.backend.backup
        def change_context(document):
            result = original(document)
            (self.folder / 'PARAM.SFO').write_bytes(self.identity + b'\0')
            return result
        with patch.object(self.backend, 'backup', side_effect=change_context), self.assertRaises(SaveError):
            self.backend.save_as(self.document, {}, self.folder / 'raced.bin')
        self.assertFalse((self.folder / 'raced.bin').exists())

    def test_snapshot_immutability_and_other_game_documents(self):
        other = pw2 if self.backend is pw1 else pw1
        for document in (replace(self.document, context_digest='broken'),
                         replace(self.document, source=None),
                         replace(self.document, format=other.FORMAT),
                         replace(self.document, native_directory='foreign')):
            with self.assertRaises(SaveError):
                self.adapter.serialize(document, {})

    def test_saved_copy_rejects_postwrite_or_readback_companion_changes(self):
        output = self.folder / 'output'
        output.mkdir()
        companion = output / 'PARAM.SFO'
        original_write = self.backend.atomic_new
        original_read = self.backend.read_save
        for phase in ('write', 'read'):
            with self.subTest(phase=phase):
                companion.write_bytes(self.identity)
                destination = output / (phase + '.bin')
                def write(data, path):
                    result = original_write(data, path)
                    if phase == 'write' and Path(path) == destination:
                        companion.write_bytes(self.identity + b'\0')
                    return result
                def read(path, *args):
                    result = original_read(path, *args)
                    if phase == 'read' and Path(path) == destination:
                        companion.write_bytes(self.identity + b'\0')
                    return result
                with patch.object(self.backend, 'atomic_new', side_effect=write), \
                        patch.object(self.backend, 'read_save', side_effect=read), \
                        self.assertRaises(SaveError):
                    self.backend.save_as(self.document, {}, destination)
                self.assertEqual(self.source.read_bytes(), self.raw)
                self.assertEqual((self.folder / 'PARAM.SFO').read_bytes(), self.identity)

    def test_restore_reopens_saved_bytes_and_pins_original_destination_context(self):
        from koei_editor.shared import copy_storage
        backup = self.adapter.backup(self.document)
        output = self.folder / 'restore'
        output.mkdir()
        companion = output / 'PARAM.SFO'
        original_write = copy_storage.atomic_new
        for change in ('context', 'payload'):
            with self.subTest(change=change):
                companion.write_bytes(self.identity)
                destination = output / (change + '.bin')
                def write(data, path):
                    result = original_write(data, path)
                    if Path(path) == destination:
                        if change == 'context':
                            companion.write_bytes(self.identity + b'\0')
                        else:
                            damaged = bytearray(destination.read_bytes())
                            damaged[-1] ^= 1  # Header still qualifies; full SHA must fail.
                            destination.write_bytes(damaged)
                    return result
                with patch.object(copy_storage, 'atomic_new', side_effect=write), self.assertRaises(SaveError):
                    self.backend.restore(backup, destination)
                self.assertEqual(backup.read_bytes(), self.raw)
                self.assertEqual(self.source.read_bytes(), self.raw)
                self.assertEqual((self.folder / 'PARAM.SFO').read_bytes(), self.identity)


class PW1PS3Tests(ProfileChecks, unittest.TestCase):
    backend = pw1


class PW2PS3Tests(ProfileChecks, unittest.TestCase):
    backend = pw2


class NativePirateWarriorsTests(unittest.TestCase):
    def _check(self, backend, variable):
        path = os.environ.get(variable)
        if not path:
            self.skipTest('Optional privately held decrypted PS3 copy unavailable')
        adapter = BoundScalarAdapter(backend.GAME_ID, '.bin', backend)
        document = adapter.read_save(Path(path))
        self.assertEqual(adapter.serialize(document, {}), document.raw)
        fields = adapter.fields_for(document)
        self.assertTrue(fields)
        for field in fields:
            opened = field.value(document.payload)
            if opened:
                output = adapter.serialize(document, {field.id: opened - 1})
                self.assertEqual(field.value(output), opened - 1)
                self.assertLessEqual({i for i, (a, b) in enumerate(zip(output, document.raw)) if a != b},
                                     set(range(field.offset, field.offset + field.size)))
        self.assertEqual(Path(path).read_bytes(), document.raw)
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = folder / 'DATA.BIN'
            source.write_bytes(document.raw)
            (folder / 'PARAM.SFO').write_bytes(backend.context_raw(Path(path)))
            copied = adapter.read_save(source)
            field = next(field for field in adapter.fields_for(copied) if field.value(copied.raw))
            opened = field.value(copied.raw)
            snapshot = adapter.backup(copied)
            edited = adapter.save_as(copied, {field.id: opened - 1}, folder / 'edited.bin')
            self.assertEqual(field.value(edited.raw), opened - 1)
            restored = adapter.restore(snapshot, folder / 'restored.bin')
            self.assertEqual(restored.read_bytes(), copied.raw)
            self.assertEqual(source.read_bytes(), copied.raw)
        self.assertEqual(Path(path).read_bytes(), document.raw)

    def test_pw1_native_copy(self):
        self._check(pw1, 'PW1_PS3_NATIVE_COPY')

    def test_pw2_native_copy(self):
        self._check(pw2, 'PW2_PS3_NATIVE_COPY')
