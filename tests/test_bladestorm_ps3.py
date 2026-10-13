"""Procedural Bladestorm storage checks, with optional original export copies."""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.bladestorm_ps3 import parser
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import BoundScalarAdapter


def fixture():
    raw = bytearray((index * 31 + 7) % 256 for index in range(parser.SAVE_SIZE))
    for offset, value in parser.HEADER_SEGMENTS:
        raw[offset:offset + len(value)] = value
    raw[0x84:0x88] = (123456).to_bytes(4, 'big')
    for index in range(16):
        offset = 0x394 + index * 0x54
        raw[offset:offset + 4] = (index * 101).to_bytes(4, 'big')
    return bytes(raw)


class BladestormPS3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = fixture()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.source = self.folder / 'PLAYDATA.bin'
        self.source.write_bytes(self.raw)
        (self.folder / 'PARAM.SFO').write_bytes(parser.identity_metadata('BLES00113PLAY0'))
        self.adapter = BoundScalarAdapter(parser.GAME_ID, '.bin', parser)
        self.document = self.adapter.read_save(self.source)

    def test_bound_noop_each_resource_surgical_readback_and_secondary_preserved(self):
        self.assertEqual(self.adapter.serialize(self.document, {}), self.raw)
        self.assertEqual(len(parser.fields_for(self.document)), 16)
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
                self.assertEqual(output[0xAB8:0xABC], self.raw[0xAB8:0xABC])
                self.assertEqual(output[0xAD4:], self.raw[0xAD4:])
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_dependency_gate_zero_sp_unknown_fields_and_complete_pending_map(self):
        self.assertNotIn('book_0_sp', parser.field_map(self.document))
        for changes in ({'book_0_sp': 1}, {'secondary_money': 1}, {'ownership': 1},
                        {'money': True}, {'money': -1}, {'money': 123457},
                        {'book_1_sp': 102}, {'money': 12, 'book_1_sp': '1'}, None, []):
            with self.subTest(changes=changes), self.assertRaises(SaveError):
                self.adapter.serialize(self.document, changes)
        with self.assertRaises(SaveError):
            self.adapter.stage(self.document, {'unknown': 1}, 'money', 1)
        output = self.adapter.serialize(self.document, {'book_1_sp': 0, 'money': 0})
        self.assertNotIn('book_1_sp', parser.field_map(parser.decode(output)))
        self.assertEqual(output[0x374:0x394], self.raw[0x374:0x394])
        self.assertEqual(parser.maximums(self.document, {'money': 12}), {'money': 12})
        self.assertEqual(parser.limit_values(self.document, {}, ('money', 'book_1_sp')), {})

    def test_unusual_opened_values_exact_typed_noop(self):
        raw = bytearray(self.raw)
        raw[0x84:0x88] = b'\xff' * 4
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
        for identity in ('BLUS30070PLAY0', 'BLES00113SYSTEM', 'BLES00113PLAYXX', 'BLES00113PLAY00', 'BLJM61251PLAY0'):
            (self.folder / 'PARAM.SFO').write_bytes(parser.identity_metadata(identity))
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
        edited = self.adapter.save_as(self.document, {'money': 11, 'book_1_sp': 4}, self.folder / 'edited.bin')
        self.assertEqual(parser.field_map(edited)['money'].value(edited.raw), 11)
        self.assertEqual(self.source.read_bytes(), self.raw)
        restored = self.adapter.restore(backup, self.folder / 'restored.bin')
        self.assertEqual(restored.read_bytes(), self.raw)
        with self.assertRaises(FileExistsError):
            self.adapter.save_as(self.document, {}, edited.source)
        with self.assertRaises(FileExistsError):
            self.adapter.save_as(self.document, {}, self.source)
        (self.folder / 'PARAM.SFO').write_bytes(parser.identity_metadata('BLES00113PLAY1'))
        with self.assertRaises(SaveError):
            self.adapter.restore(backup, self.folder / 'wrong-context.bin')

    def test_source_and_context_changes_guard_final_write(self):
        original = parser.serialize
        def mutate(document, changes):
            output = original(document, changes)
            self.source.write_bytes(self.raw[:-1])
            return output
        with patch.object(parser, 'serialize', side_effect=mutate), self.assertRaises(SaveError):
            parser.save_as(self.document, {'money': 11}, self.folder / 'race.bin')
        self.assertFalse((self.folder / 'race.bin').exists())
        self.source.write_bytes(self.raw)
        original_backup = parser.backup
        def mutate_context(document):
            result = original_backup(document)
            (self.folder / 'PARAM.SFO').write_bytes(parser.identity_metadata('BLES00113PLAY1'))
            return result
        with patch.object(parser, 'backup', side_effect=mutate_context), self.assertRaises(SaveError):
            parser.save_as(self.document, {'money': 11}, self.folder / 'context-race.bin')
        self.assertFalse((self.folder / 'context-race.bin').exists())

    def test_integrity_evidence_does_not_claim_unmapped_checksum_detection(self):
        self.assertEqual(parser.INTEGRITY_KIND, 'external')
        raw = bytearray(self.raw)
        raw[-1] ^= 1
        self.assertEqual(parser.serialize(parser.decode(bytes(raw)), {}), bytes(raw))


    def test_postwrite_same_title_context_replacement_rejected_for_save_and_restore(self):
        original_context = (self.folder / 'PARAM.SFO').read_bytes()
        changes = {'money': 11}
        expected_edit = parser.serialize(self.document, changes)
        backup = self.adapter.backup(self.document)
        for operation in ('save', 'restore'):
            for timing in ('after write', 'after reopen'):
                with self.subTest(operation=operation, timing=timing):
                    folder = self.folder / (operation + '-' + timing.replace(' ', '-'))
                    folder.mkdir()
                    companion = folder / 'PARAM.SFO'
                    companion.write_bytes(original_context)
                    destination = folder / 'written.bin'
                    mutation_triggered = False
                    def replace_context():
                        nonlocal mutation_triggered
                        # Same native title/directory remains valid; only the
                        # opaque original companion binding has changed.
                        companion.write_bytes(original_context + b'same-title-context-race')
                        mutation_triggered = True
                    if timing == 'after write':
                        method = 'atomic_new' if operation == 'save' else 'restore_snapshot'
                        original = getattr(parser, method)
                        def mutate(*args, **kwargs):
                            result = original(*args, **kwargs)
                            if Path(args[1]).resolve() == destination.resolve():
                                replace_context()
                            return result
                    else:
                        method = 'read_save'
                        original = parser.read_save
                        def mutate(*args, **kwargs):
                            result = original(*args, **kwargs)
                            if Path(args[0]).resolve() == destination.resolve():
                                replace_context()
                            return result
                    with patch.object(parser, method, side_effect=mutate), self.assertRaises(SaveError):
                        if operation == 'save':
                            self.adapter.save_as(self.document, changes, destination)
                        else:
                            self.adapter.restore(backup, destination)
                    self.assertTrue(mutation_triggered, 'Companion fault injection did not fire.')
                    # A raced destination may have been replaced by another
                    # actor; failure must not delete that new path.
                    self.assertEqual(destination.read_bytes(), expected_edit if operation == 'save' else self.raw)
                    self.assertEqual(self.source.read_bytes(), self.raw)
                    self.assertEqual((self.folder / 'PARAM.SFO').read_bytes(), original_context)

    def test_source_change_after_atomic_write_rejected_without_repair(self):
        changes = {'money': 11}
        destination = self.folder / 'postwrite-source-race.bin'
        expected_edit = parser.serialize(self.document, changes)
        original = parser.atomic_new
        mutation_triggered = False
        def mutate(raw, target):
            nonlocal mutation_triggered
            result = original(raw, target)
            if Path(target).resolve() == destination.resolve():
                self.source.write_bytes(self.raw[:-1])
                mutation_triggered = True
            return result
        with patch.object(parser, 'atomic_new', side_effect=mutate), self.assertRaises(SaveError):
            self.adapter.save_as(self.document, changes, destination)
        self.assertTrue(mutation_triggered, 'Source fault injection did not fire.')
        self.assertEqual(self.source.read_bytes(), self.raw[:-1])
        self.assertEqual(destination.read_bytes(), expected_edit)


@unittest.skipUnless(os.environ.get('BLADESTORM_PS3_NATIVE_DIR'), 'Optional original EU decrypted exports unavailable')
class NativeBladestormTests(unittest.TestCase):
    def test_unchanged_and_surgical_resource_readback(self):
        files = sorted(Path(os.environ['BLADESTORM_PS3_NATIVE_DIR']).rglob('PLAYDATA.bin'))
        self.assertTrue(files)
        adapter = BoundScalarAdapter(parser.GAME_ID, '.bin', parser)
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
