"""Procedural Attack on Titan Vita storage checks, with optional original export copies."""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.aot1_vita import parser
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import BoundScalarAdapter


def fixture():
    raw = bytearray((index * 31 + 7) % 256 for index in range(parser.SAVE_SIZE))
    for offset, value in parser.HEADER_SEGMENTS:
        raw[offset:offset + len(value)] = value
    raw[0x34:0x38] = (123456).to_bytes(4, 'little')
    for index in range(81):
        offset = 0x35CA0 + index * 0x30
        raw[offset:offset + 2] = (index * 101).to_bytes(2, 'little')
    return bytes(raw)


class AOT1VitaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = fixture()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.source = self.folder / 'app0000.dat'
        self.source.write_bytes(self.raw)
        (self.folder / 'sce_sys').mkdir()
        (self.folder / 'sce_sys/param.sfo').write_bytes(parser.identity_metadata('/PCSB00898'))
        self.adapter = BoundScalarAdapter(parser.GAME_ID, '.dat', parser)
        self.document = self.adapter.read_save(self.source)

    def test_bound_noop_each_resource_surgical_readback_and_other_records_preserved(self):
        self.assertEqual(self.adapter.serialize(self.document, {}), self.raw)
        self.assertEqual(len(parser.fields_for(self.document)), 81)
        for field in parser.fields_for(self.document):
            original = field.value(self.raw)
            with self.subTest(field=field.id):
                changes = self.adapter.stage(self.document, {}, field.id, original // 2)
                self.assertEqual(self.adapter.stage(self.document, changes, field.id, original), {})
                self.assertEqual(len(self.adapter.review(self.document, changes)), 1)
                output = self.adapter.serialize(self.document, changes)
                self.assertEqual(field.value(output), original // 2)
                touched = {i for i, (a, b) in enumerate(zip(self.raw, output)) if a != b}
                self.assertLessEqual(touched, set(range(field.offset, field.offset + field.size)))
                self.assertEqual(output[field.offset + field.size:], self.raw[field.offset + field.size:])
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_dependency_gate_zero_material_unknown_fields_and_complete_pending_map(self):
        self.assertNotIn('material_0_quantity', parser.field_map(self.document))
        for changes in ({'material_0_quantity': 1}, {'secondary_money': 1}, {'ownership': 1},
                        {'money': True}, {'money': -1}, {'money': 123457},
                        {'material_1_quantity': 102}, {'money': 12, 'material_1_quantity': '1'}, None, []):
            with self.subTest(changes=changes), self.assertRaises(SaveError):
                self.adapter.serialize(self.document, changes)
        with self.assertRaises(SaveError):
            self.adapter.stage(self.document, {'unknown': 1}, 'money', 1)
        output = self.adapter.serialize(self.document, {'material_1_quantity': 0, 'money': 0})
        self.assertNotIn('material_1_quantity', parser.field_map(parser.decode(output)))
        self.assertEqual(output[0x35CA0 - 16:0x35CA0], self.raw[0x35CA0 - 16:0x35CA0])
        self.assertEqual(parser.maximums(self.document, {'money': 12}), {'money': 12})
        self.assertEqual(parser.limit_values(self.document, {}, ('money', 'material_1_quantity')), {})

    def test_unusual_opened_values_exact_typed_noop(self):
        raw = bytearray(self.raw)
        raw[0x34:0x38] = b'\xff' * 4
        document = parser.decode(bytes(raw))
        self.assertEqual(self.adapter.stage(document, {}, 'money', 0xFFFFFFFF), {})
        self.assertEqual(self.adapter.serialize(document, {'money': 0xFFFFFFFF}), bytes(raw))
        with self.assertRaises(SaveError):
            self.adapter.stage(document, {}, 'money', 0xFFFFFFFF * 1.0)
        self.assertEqual(self.adapter.maximums(document, {}), {})

    def test_header_size_wrong_identity_and_frozen_documents(self):
        for offset, marker in parser.HEADER_SEGMENTS:
            raw = bytearray(self.raw)
            raw[offset] ^= 1
            with self.assertRaises(SaveError):
                parser.decode(bytes(raw))
        for raw in (self.raw[:-1], self.raw + b'\0', bytearray(self.raw), bytes(len(self.raw))):
            with self.assertRaises(SaveError):
                parser.decode(raw)
        for identity in ('/PCSE00812', '/PCSB00898_SLOT0', 'PCSB00898', '/PCSB01085', '/PCSB008980'):
            (self.folder / 'sce_sys/param.sfo').write_bytes(parser.identity_metadata(identity))
            with self.assertRaises(SaveError):
                self.adapter.read_save(self.source)
        for document in (replace(self.document, payload=self.raw[:-1]),
                         replace(self.document, format=replace(parser.FORMAT, id='foreign')),
                         replace(self.document, source=None),
                         replace(self.document, native_directory='foreign')):
            with self.assertRaises(SaveError):
                self.adapter.serialize(document, {})

    def test_safe_storage_context_restore_and_existing_destination(self):
        backup = self.adapter.backup(self.document)
        edited = self.adapter.save_as(self.document, {'money': 11, 'material_1_quantity': 4}, self.folder / 'edited.dat')
        self.assertEqual(parser.field_map(edited)['money'].value(edited.raw), 11)
        self.assertEqual(self.source.read_bytes(), self.raw)
        restored = self.adapter.restore(backup, self.folder / 'restored.dat')
        self.assertEqual(restored.read_bytes(), self.raw)
        with self.assertRaises(FileExistsError):
            self.adapter.save_as(self.document, {}, edited.source)
        with self.assertRaises(FileExistsError):
            self.adapter.save_as(self.document, {}, self.source)
        (self.folder / 'sce_sys/param.sfo').write_bytes(parser.identity_metadata('/PCSB00899'))
        with self.assertRaises(SaveError):
            self.adapter.restore(backup, self.folder / 'wrong-context.dat')

    def test_source_and_context_changes_guard_final_write(self):
        original = parser.serialize
        def mutate(document, changes):
            output = original(document, changes)
            self.source.write_bytes(self.raw[:-1])
            return output
        with patch.object(parser, 'serialize', side_effect=mutate), self.assertRaises(SaveError):
            parser.save_as(self.document, {'money': 11}, self.folder / 'race.dat')
        self.assertFalse((self.folder / 'race.dat').exists())
        self.source.write_bytes(self.raw)
        original_backup = parser.backup
        def mutate_context(document):
            result = original_backup(document)
            (self.folder / 'sce_sys/param.sfo').write_bytes(parser.identity_metadata('/PCSB00899'))
            return result
        with patch.object(parser, 'backup', side_effect=mutate_context), self.assertRaises(SaveError):
            parser.save_as(self.document, {'money': 11}, self.folder / 'context-race.dat')
        self.assertFalse((self.folder / 'context-race.dat').exists())

    def test_integrity_evidence_does_not_claim_unmapped_checksum_detection(self):
        self.assertEqual(parser.INTEGRITY_KIND, 'external')
        raw = bytearray(self.raw)
        raw[-1] ^= 1
        self.assertEqual(parser.serialize(parser.decode(bytes(raw)), {}), bytes(raw))

    def test_postwrite_and_readback_context_changes_reject_saved_copy(self):
        output = self.folder / 'output'
        (output / 'sce_sys').mkdir(parents=True)
        companion = output / 'sce_sys/param.sfo'
        identity = (self.folder / 'sce_sys/param.sfo').read_bytes()
        original_write, original_read = parser.atomic_new, parser.read_save
        for phase in ('write', 'read'):
            with self.subTest(phase=phase):
                companion.write_bytes(identity)
                destination = output / (phase + '.dat')
                mutations = []
                def write(data, path):
                    result = original_write(data, path)
                    if phase == 'write' and Path(path).resolve() == destination.resolve():
                        companion.write_bytes(identity + b'\0')
                        mutations.append(phase)
                    return result
                def read(path, *args):
                    result = original_read(path, *args)
                    if phase == 'read' and Path(path).resolve() == destination.resolve():
                        companion.write_bytes(identity + b'\0')
                        mutations.append(phase)
                    return result
                with patch.object(parser, 'atomic_new', side_effect=write), \
                        patch.object(parser, 'read_save', side_effect=read), self.assertRaises(SaveError):
                    parser.save_as(self.document, {'money': 11}, destination)
                self.assertEqual(mutations, [phase], 'The requested companion mutation must execute.')
                self.assertEqual(self.source.read_bytes(), self.raw)
                self.assertEqual((self.folder / 'sce_sys/param.sfo').read_bytes(), identity)

    def test_restore_verifies_actual_saved_bytes_and_complete_original_context(self):
        from koei_editor.shared import copy_storage
        backup = parser.backup(self.document)
        output = self.folder / 'restore'
        (output / 'sce_sys').mkdir(parents=True)
        companion = output / 'sce_sys/param.sfo'
        identity = (self.folder / 'sce_sys/param.sfo').read_bytes()
        original_write = copy_storage.atomic_new
        for change in ('context', 'payload'):
            with self.subTest(change=change):
                companion.write_bytes(identity)
                destination = output / (change + '.dat')
                mutations = []
                def write(data, path):
                    result = original_write(data, path)
                    if Path(path).resolve() == destination.resolve():
                        if change == 'context':
                            companion.write_bytes(identity + b'\0')
                        else:
                            damaged = bytearray(destination.read_bytes())
                            damaged[-1] ^= 1
                            destination.write_bytes(damaged)
                        mutations.append(change)
                    return result
                with patch.object(copy_storage, 'atomic_new', side_effect=write), self.assertRaises(SaveError):
                    parser.restore(backup, destination)
                self.assertEqual(mutations, [change], 'The requested restore mutation must execute.')
                self.assertEqual(backup.read_bytes(), self.raw)
                self.assertEqual(self.source.read_bytes(), self.raw)
                self.assertEqual((self.folder / 'sce_sys/param.sfo').read_bytes(), identity)


@unittest.skipUnless(os.environ.get('AOT1_VITA_NATIVE_DIR'), 'Optional original EU decrypted exports unavailable')
class NativeAOT1VitaTests(unittest.TestCase):
    def test_unchanged_and_surgical_resource_readback(self):
        files = sorted(Path(os.environ['AOT1_VITA_NATIVE_DIR']).rglob('app0000.dat'))
        self.assertTrue(files)
        adapter = BoundScalarAdapter(parser.GAME_ID, '.dat', parser)
        for source in files:
            with self.subTest(source=source.name):
                document = adapter.read_save(source)
                self.assertEqual(adapter.serialize(document, {}), document.raw)
                for field in adapter.fields_for(document):
                    value = field.value(document.raw)
                    if not value:
                        continue
                    output = adapter.serialize(document, {field.id: value - 1})
                    self.assertEqual(field.value(output), value - 1)
                    touched = {i for i, (a, b) in enumerate(zip(document.raw, output)) if a != b}
                    self.assertLessEqual(touched, set(range(field.offset, field.offset + field.size)))
                self.assertEqual(source.read_bytes(), document.raw)
