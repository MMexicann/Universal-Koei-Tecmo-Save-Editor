"""Exact EU PS3 PW3 procedural safety and optional native reference checks."""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.pw3_ps3 import parser
from koei_editor.shared.adapter_contract import BoundScalarAdapter


def fixture():
    raw = bytearray((i * 29 + 13) % 256 for i in range(parser.SAVE_SIZE))
    for offset, value in parser.HEADER_SEGMENTS:
        raw[offset:offset + len(value)] = value
    for index in range(parser.RECORD_COUNT):
        base = index * parser.RECORD_STRIDE
        raw[0xF0 + base:0xF4 + base] = (10000 + index).to_bytes(4, 'big')
        for offset, value in ((0xF4, 4000), (0xF6, 300), (0xF8, 200)):
            raw[offset + base:offset + base + 2] = value.to_bytes(2, 'big')
        raw[0xFB + base] = 40
    return bytes(raw)


class PW3PS3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = fixture()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.source = self.folder / 'DATA.BIN'
        self.source.write_bytes(self.raw)
        (self.folder / 'PARAM.SFO').write_bytes(parser.identity_metadata('NPEB02211-00'))
        self.adapter = BoundScalarAdapter(parser.GAME_ID, '.bin', parser)
        self.document = self.adapter.read_save(self.source)

    def test_all_fields_exact_noop_unstage_review_surgical_readback(self):
        self.assertEqual(len(self.adapter.fields_for(self.document)), 141)
        self.assertEqual(self.adapter.serialize(self.document, {}), self.raw)
        for field in self.adapter.fields_for(self.document):
            with self.subTest(field=field.id):
                original = field.value(self.raw)
                changes = self.adapter.stage(self.document, {}, field.id, original - 1)
                self.assertEqual(self.adapter.stage(self.document, changes, field.id, original), {})
                output = self.adapter.serialize(self.document, changes)
                self.assertEqual(field.value(output), original - 1)
                self.assertEqual(len(self.adapter.review(self.document, changes)), 1)
                touched = {i for i, (a, b) in enumerate(zip(self.raw, output)) if a != b}
                self.assertLessEqual(touched, set(range(field.offset, field.offset + 2)))
                self.assertEqual(output[0xC074:0xC07C], self.raw[0xC074:0xC07C])
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_progression_eligibility_and_no_zero_stat_creation(self):
        for offset, value in ((0xFB, 0), (0xFB, 100), (0xF0, 0)):
            raw = bytearray(self.raw)
            if offset == 0xF0:
                raw[offset:offset + 4] = value.to_bytes(4, 'big')
            else:
                raw[offset] = value
            document = parser.decode(bytes(raw))
            self.assertFalse(any(f.id.startswith('character_0_') for f in parser.fields_for(document)))
            with self.assertRaises(SaveError):
                self.adapter.serialize(document, {'character_0_hp': 100})
        raw = bytearray(self.raw)
        raw[0xF6:0xF8] = bytes(2)
        document = parser.decode(bytes(raw))
        self.assertNotIn('character_0_attack', parser.field_map(document))
        with self.assertRaises(SaveError):
            self.adapter.serialize(self.document, {'character_0_hp': 0})
        self.assertEqual(parser.maximums(self.document, {'character_0_hp': 3}), {'character_0_hp': 3})
        self.assertEqual(parser.limit_values(self.document, {}, ['character_0_hp']), {})

    def test_invalid_complete_pending_maps_and_unusual_original(self):
        for changes in (None, [], {'money': 1}, {'character_0_hp': True},
                        {'character_0_attack': 301}, {'character_0_defense': -1},
                        {'character_0_hp': 4, 'xp': 1}):
            with self.subTest(changes=changes), self.assertRaises(SaveError):
                self.adapter.serialize(self.document, changes)
        raw = bytearray(self.raw)
        raw[0xF4:0xF6] = b'\xff\xff'
        document = parser.decode(bytes(raw))
        self.assertEqual(self.adapter.stage(document, {}, 'character_0_hp', 65535), {})
        self.assertEqual(self.adapter.serialize(document, {'character_0_hp': 65535}), bytes(raw))
        with self.assertRaises(SaveError):
            self.adapter.stage(document, {}, 'character_0_hp', 65535.0)

    def test_geometry_header_title_context_and_frozen_documents(self):
        for raw in (self.raw[:-1], self.raw + b'\0', bytearray(self.raw), bytes(parser.SAVE_SIZE)):
            with self.assertRaises(SaveError):
                parser.decode(raw)
        for offset, marker in parser.HEADER_SEGMENTS:
            raw = bytearray(self.raw)
            raw[offset] ^= 1
            with self.assertRaises(SaveError):
                parser.decode(bytes(raw))
        for identity in ('NPUB31676-00', 'NPEB02211-01', 'BLES02140-00', 'NPEB01795-00'):
            (self.folder / 'PARAM.SFO').write_bytes(parser.identity_metadata(identity))
            with self.assertRaises(SaveError):
                self.adapter.read_save(self.source)
        for document in (replace(self.document, payload=self.raw[:-1]),
                         replace(self.document, format=replace(parser.FORMAT, id='pw3')),
                         replace(self.document, native_directory='foreign')):
            with self.assertRaises(SaveError):
                self.adapter.serialize(document, {})

    def test_source_context_atomic_save_backup_restore(self):
        backup = self.adapter.backup(self.document)
        edited = self.adapter.save_as(self.document, {'character_0_hp': 100}, self.folder / 'edited.bin')
        self.assertEqual(parser.field_map(edited)['character_0_hp'].value(edited.raw), 100)
        restored = self.adapter.restore(backup, self.folder / 'restored.bin')
        self.assertEqual(restored.read_bytes(), self.raw)
        with self.assertRaises(FileExistsError):
            self.adapter.save_as(self.document, {}, edited.source)
        self.source.write_bytes(self.raw[:-1])
        with self.assertRaises(SaveError):
            self.adapter.save_as(self.document, {}, self.folder / 'changed-source.bin')
        self.source.write_bytes(self.raw)
        (self.folder / 'PARAM.SFO').write_bytes(parser.identity_metadata('NPEB02211-00') + b'opaque metadata change')
        with self.assertRaises(SaveError):
            self.adapter.save_as(self.document, {}, self.folder / 'changed-context.bin')
        with self.assertRaises(SaveError):
            self.adapter.restore(backup, self.folder / 'changed-context-restore.bin')
        self.assertFalse((self.folder / 'changed-context.bin').exists())


    def test_postwrite_same_title_context_replacement_rejected_for_save_and_restore(self):
        original_context = (self.folder / 'PARAM.SFO').read_bytes()
        changes = {'character_0_hp': 100}
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
        changes = {'character_0_hp': 100}
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


@unittest.skipUnless(os.environ.get('PW3_PS3_NATIVE_DIR'), 'Optional original EU decrypted reference unavailable')
class NativePW3PS3Tests(unittest.TestCase):
    def test_reference_noop_each_eligible_stat_surgical_readback(self):
        source = Path(os.environ['PW3_PS3_NATIVE_DIR']) / 'DATA.BIN'
        adapter = BoundScalarAdapter(parser.GAME_ID, '.bin', parser)
        document = adapter.read_save(source)
        self.assertEqual(adapter.serialize(document, {}), document.raw)
        fields = adapter.fields_for(document)
        self.assertTrue(fields)
        for field in fields:
            original = field.value(document.raw)
            output = adapter.serialize(document, {field.id: max(field.minimum, original - 1)})
            self.assertEqual(field.value(output), max(field.minimum, original - 1))
            touched = {i for i, (a, b) in enumerate(zip(document.raw, output)) if a != b}
            self.assertLessEqual(touched, set(range(field.offset, field.offset + 2)))
        self.assertEqual(source.read_bytes(), document.raw)
