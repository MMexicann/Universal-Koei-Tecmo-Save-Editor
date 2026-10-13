"""Procedural format/safety checks; genuine exports are private optional inputs."""
from dataclasses import replace
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.gundam1_ps3 import parser
from tests.scalar_contract import ScalarContractTests


def metadata(directory='BLUS30058-00'):
    key = b'SAVEDATA_DIRECTORY\0'
    value = directory.encode('ascii') + b'\0'
    return (struct.pack('<5I', 0x46535000, 0x101, 36, 36 + len(key), 1)
            + struct.pack('<HH3I', 0, 0x204, len(value), len(value), 0) + key + value)


def fixture():
    payload = bytearray((i * 13 + 17) % 256 for i in range(parser.SAVE_SIZE))
    payload[:4] = parser.REVISION
    payload[0x14:0x1C] = bytes.fromhex('0000002000001dd2')
    for _, _, offset in parser.PILOTS:
        payload[offset:offset + 4] = (0xFFFFFFFF).to_bytes(4, 'big')
        payload[offset + 16] = 29
        payload[offset + 23:offset + 29] = bytes(6)
        payload[offset + 29:offset + 36] = bytes.fromhex('01000000a01122')
    return parser.seal(bytes(payload))


class Gundam1PS3ContractTests(ScalarContractTests, unittest.TestCase):
    game_id = parser.GAME_ID
    fixture_bytes = staticmethod(fixture)
    payload_integrity_offsets = frozenset(i for offset in parser.CHECKSUM_OFFSETS
                                          for i in range(offset, offset + 4))

    def setUp(self):
        from koei_editor.game_registry import get_game
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name).resolve()
        (self.folder / 'PARAM.SFO').write_bytes(metadata())
        self.game = get_game(self.game_id)
        self.adapter = self.game.get_scalar_adapter()
        self.raw = self.fixture_bytes()
        self.source = self.folder / 'input-copy.bin'
        self.source.write_bytes(self.raw)
        self.document = self.adapter.read_save(self.source)


class Gundam1PS3Tests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        # The backend resolves Windows 8.3 aliases before its atomic write hooks.
        # Derive every test path from that same canonical folder so faults fire.
        self.folder = Path(folder.name).resolve()
        self.source = self.folder / 'DATA.BIN'
        self.source.write_bytes(fixture())
        (self.folder / 'PARAM.SFO').write_bytes(metadata())
        self.document = parser.read_save(self.source)

    def test_all_published_pilots_all36_flags_surgical_roundtrip(self):
        self.assertEqual(len(parser.fields_for(self.document)), 216)
        self.assertEqual(parser.serialize(self.document, {}), self.document.raw)
        integrity = {i for offset in parser.CHECKSUM_OFFSETS for i in range(offset, offset + 4)}
        for field in parser.fields_for(self.document):
            if field.value(self.document.payload):
                continue
            with self.subTest(field=field.id):
                changes = parser.stage(self.document, {}, field.id, 1)
                raw = parser.serialize(self.document, changes)
                reopened = parser.decode(raw, source=self.source)
                self.assertEqual(field.value(raw), 1)
                self.assertEqual(reopened.payload, parser.changed_payload(self.document, changes))
                touched = {i for i, (a, b) in enumerate(zip(raw, self.document.raw)) if a != b}
                self.assertLessEqual(touched, integrity | {field.offset})
                self.assertEqual(raw[field.offset] ^ self.document.raw[field.offset], 1 << field.bit)
        self.assertEqual(self.source.read_bytes(), fixture())

    def test_learning_only_stage_unstage_review_no_max_and_batch_bits(self):
        changes = parser.stage(self.document, {}, 'amuro_skill_1', 1)
        changes = parser.stage(self.document, changes, 'amuro_skill_2', 1)
        self.assertEqual(parser.stage(self.document, changes, 'amuro_skill_1', 0), {'amuro_skill_2': 1})
        self.assertEqual(len(parser.review(self.document, changes)), 2)
        self.assertEqual(parser.maximums(self.document, changes), changes)
        self.assertEqual(parser.limit_values(self.document, changes, changes), {})
        raw = parser.serialize(self.document, changes)
        self.assertEqual(raw[0x1A5], 7)
        self.assertEqual(raw[0x1A9:0x1AC], bytes.fromhex('a01122'))
        self.assertEqual(raw[0x188:0x18C], b'\xff' * 4)
        with self.assertRaises(SaveError):
            parser.stage(self.document, {}, 'amuro_skill_0', 0)
        self.assertEqual(parser.stage(self.document, {}, 'amuro_skill_0', 1), {})

    def test_corrupt_integrity_structure_size_and_foreign_identity(self):
        for offset in (8, 12, 16, 0x20, 0x1A5, 0x1FFF, 0x2000, 0x88DCF, 0x88DD0, parser.SAVE_SIZE - 1):
            raw = bytearray(self.document.raw)
            raw[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(SaveError):
                parser.decode(bytes(raw), source=self.source)
        for raw in (self.document.raw[:-1], self.document.raw + b'\0', b'\xff' * parser.SAVE_SIZE,
                    bytearray(self.document.raw)):
            with self.assertRaises(SaveError):
                parser.decode(raw, source=self.source)
        for offset in (0, 0x14, 0x18):
            raw = bytearray(self.document.raw)
            raw[offset] ^= 1
            with self.assertRaises(SaveError):
                parser.decode(parser.seal(bytes(raw)), source=self.source)
        for identity in ('BLUS30288-00', 'BLJM60018-00', 'BLUS30058-00-extra', 'BLUS30058-X1'):
            (self.folder / 'PARAM.SFO').write_bytes(metadata(identity))
            with self.assertRaises(SaveError):
                parser.read_save(self.source)

    def test_missing_identity_and_conflicting_output_do_not_write(self):
        (self.folder / 'PARAM.SFO').unlink()
        with self.assertRaises(SaveError):
            parser.read_save(self.source)
        (self.folder / 'PARAM.SFO').write_bytes(metadata())
        other = self.folder / 'other'
        other.mkdir()
        destination = other / 'edited.bin'
        with self.assertRaises(SaveError):
            parser.save_as(self.document, {}, destination)
        (other / 'PARAM.SFO').write_bytes(metadata('BLES00147-00'))
        with self.assertRaises(SaveError):
            parser.save_as(self.document, {}, destination)
        self.assertFalse(destination.exists())
        (self.folder / 'PARAM.SFO').write_bytes(metadata('BLUS30058-02'))
        with self.assertRaises(SaveError):
            parser.save_as(self.document, {}, self.folder / 'changed-context.bin')

    def test_unqualified_records_and_unknown_higher_bits_preserved(self):
        raw = bytearray(self.document.raw)
        raw[0x198] = 250
        raw[0x49C + 23] = 200
        raw[0x93A + 29] = 0
        raw[0xAC4 + 16] = 28
        raw[0x10EC + 27] = 35
        raw = parser.seal(bytes(raw))
        document = parser.decode(raw, source=self.source)
        fields = parser.field_map(document)
        for key in ('amuro_skill_1', 'kamille_skill_1', 'judau_skill_1', 'domon_skill_1', 'loran_skill_1'):
            self.assertNotIn(key, fields)
            with self.assertRaises(SaveError):
                parser.stage(document, {}, key, 1)
        output = parser.serialize(document, {'heero_skill_35': 1})
        self.assertEqual(output[0x198], 250)
        self.assertEqual(output[0x49C + 23], 200)
        self.assertEqual(output[0x188:0x18C], b'\xff' * 4)
        for _, _, offset in parser.PILOTS:
            self.assertEqual(output[offset + 33] & 0xF0, raw[offset + 33] & 0xF0)
            self.assertEqual(output[offset + 34:offset + 36], raw[offset + 34:offset + 36])

    def test_invalid_fields_values_changes_and_forged_snapshot(self):
        for changes in ([], None, {'amuro_skill_36': 1}, {'exp': 1}, {'amuro_skill_1': True},
                        {'amuro_skill_1': -1}, {'amuro_skill_1': 2}, {'amuro_skill_0': 0}):
            with self.subTest(changes=changes), self.assertRaises(SaveError):
                parser.serialize(self.document, changes)
        for document in (replace(self.document, payload=bytearray(self.document.payload)),
                         replace(self.document, format=replace(parser.FORMAT, id='foreign')),
                         replace(self.document, native_directory='foreign')):
            with self.assertRaises(SaveError):
                parser.backup(document)

    def test_backups_restore_source_change_and_existing_destination(self):
        backup = parser.backup(self.document)
        destination = self.folder / 'edited.bin'
        edited = parser.save_as(self.document, {'amuro_skill_1': 1}, destination)
        self.assertEqual(parser.field_map(edited)['amuro_skill_1'].value(edited.raw), 1)
        self.assertEqual(self.source.read_bytes(), self.document.raw)
        self.assertEqual(parser.restore(backup, self.folder / 'restored.bin').read_bytes(), self.document.raw)
        with self.assertRaises(FileExistsError):
            parser.save_as(self.document, {}, destination)
        self.source.write_bytes(self.document.raw[:-1] + b'\x00')
        with self.assertRaises(SaveError):
            parser.save_as(self.document, {}, self.folder / 'changed.bin')

    def test_identity_only_self_test_companion_has_no_owner_fields(self):
        sentinel = b'OWNER-CONTEXT-MUST-NOT-BE-COPIED'
        (self.folder / 'PARAM.SFO').write_bytes(metadata() + sentinel)
        self.document = parser.read_save(self.source)
        destination = self.folder / 'self-test' / 'edited.bin'
        parser.prepare_self_test_copy(self.document, destination)
        self.assertEqual((destination.parent / 'PARAM.SFO').read_bytes(), metadata())
        parser.prepare_self_test_copy(self.document, destination)
        parser.save_as(self.document, {'amuro_skill_1': 1}, destination)
        from koei_editor.shared.verified_self_test import run
        output = self.folder / 'cli-self-test'
        report = run(parser.GAME_ID, self.source, output)
        self.assertTrue(report['success'])
        self.assertTrue(report['native_integrity_verified'])
        self.assertEqual(report['fields_changed'], 0)
        self.assertFalse(report['in_game_load_tested'])
        self.assertEqual((output / 'PARAM.SFO').read_bytes(), metadata())
        self.assertNotIn(sentinel, (output / 'self-test-report.json').read_bytes())
        self.assertEqual((self.folder / 'PARAM.SFO').read_bytes(), metadata() + sentinel)

    def test_opaque_source_companion_mutation_rejects_operations(self):
        # Title/slot remains identical; frozen source context must still match.
        (self.folder / 'PARAM.SFO').write_bytes(metadata() + b'opaque-changed-context')
        operations = (lambda: parser.backup(self.document),
                      lambda: parser.save_as(self.document, {}, self.folder / 'changed.bin'),
                      lambda: parser.prepare_self_test_copy(self.document,
                                                             self.folder / 'cli' / 'edited.bin'))
        for operation in operations:
            with self.assertRaises(SaveError):
                operation()
        self.assertFalse((self.folder / 'changed.bin').exists())
        self.assertFalse((self.folder / 'cli' / 'PARAM.SFO').exists())
        self.assertEqual(self.source.read_bytes(), self.document.raw)

    def test_final_source_and_destination_guards_after_backup(self):
        original_backup = parser.backup
        for target in ('source', 'destination'):
            with self.subTest(target=target):
                other = self.folder / target
                other.mkdir()
                (other / 'PARAM.SFO').write_bytes(metadata())
                destination = other / 'edited.bin'
                def mutate(document):
                    result = original_backup(document)
                    if target == 'source':
                        self.source.write_bytes(document.raw[:-1] + bytes([document.raw[-1] ^ 1]))
                    else:
                        (other / 'PARAM.SFO').write_bytes(metadata() + b'opaque-mutation')
                    return result
                with patch.object(parser, 'backup', side_effect=mutate), self.assertRaises(SaveError):
                    parser.save_as(self.document, {'amuro_skill_1': 1}, destination)
                self.assertFalse(destination.exists())
                self.source.write_bytes(self.document.raw)

    def test_changed_companion_during_backup_removes_partial_snapshot(self):
        original_snapshot = parser.snapshot_backup
        def mutate(*args, **kwargs):
            result = original_snapshot(*args, **kwargs)
            (self.folder / 'PARAM.SFO').write_bytes(metadata() + b'changed-during-backup')
            return result
        with patch.object(parser, 'snapshot_backup', side_effect=mutate), self.assertRaises(SaveError):
            parser.backup(self.document)
        self.assertEqual(list((self.folder / 'UniversalEditorBackups').iterdir()), [])

    def test_backup_sidecar_collision_preserves_foreign_file(self):
        original_write = parser.atomic_new
        foreign = b'foreign-sidecar-created-by-another-operation'
        collisions = []
        def collide(data, path):
            if Path(path).suffix == '.sfo':
                Path(path).write_bytes(foreign)
                collisions.append(Path(path))
                raise FileExistsError('Concurrent sidecar creation')
            return original_write(data, path)
        with patch.object(parser, 'atomic_new', side_effect=collide), self.assertRaises(FileExistsError):
            parser.backup(self.document)
        self.assertEqual(len(collisions), 1)
        self.assertEqual(collisions[0].read_bytes(), foreign)
        self.assertEqual(list((self.folder / 'UniversalEditorBackups').iterdir()), collisions)

    def test_save_rechecks_source_and_opaque_companion_after_atomic_write(self):
        original_write = parser.atomic_new
        for target in ('source', 'source-context', 'destination-context'):
            with self.subTest(target=target):
                self.source.write_bytes(self.document.raw)
                (self.folder / 'PARAM.SFO').write_bytes(metadata())
                other = self.folder / f'after-write-{target}'
                other.mkdir()
                (other / 'PARAM.SFO').write_bytes(metadata())
                destination = other / 'edited.bin'
                injected = []
                def mutate(data, path):
                    result = original_write(data, path)
                    if Path(path) == destination:
                        injected.append(destination)
                        if target == 'source':
                            self.source.write_bytes(self.document.raw[:-1] + bytes([self.document.raw[-1] ^ 1]))
                        else:
                            context = self.folder if target == 'source-context' else other
                            (context / 'PARAM.SFO').write_bytes(metadata() + b'after-write-context')
                    return result
                with patch.object(parser, 'atomic_new', side_effect=mutate), self.assertRaises(SaveError):
                    parser.save_as(self.document, {'amuro_skill_1': 1}, destination)
                self.assertEqual(injected, [destination])
                self.assertTrue(destination.exists())  # Preserve the raced path for review.

    def test_restore_postwrite_validation_preserves_raced_destination(self):
        backup = parser.backup(self.document)
        original_write = parser.atomic_new
        for target in ('destination', 'context', 'sidecar'):
            with self.subTest(target=target):
                (self.folder / 'PARAM.SFO').write_bytes(metadata())
                backup.with_suffix('.sfo').write_bytes(metadata())
                destination = self.folder / f'after-restore-{target}.bin'
                injected = []
                def mutate(data, path):
                    result = original_write(data, path)
                    if Path(path) == destination:
                        injected.append(destination)
                        if target == 'destination':
                            changed = bytearray(data)
                            changed[-1] ^= 1
                            destination.write_bytes(parser.seal(bytes(changed)))
                        else:
                            companion = self.folder / 'PARAM.SFO' if target == 'context' else backup.with_suffix('.sfo')
                            companion.write_bytes(metadata() + b'after-restore-context')
                    return result
                # Shared restore uses its own atomic helper; patch its write boundary.
                with patch('koei_editor.shared.copy_storage.atomic_new', side_effect=mutate), self.assertRaises(SaveError):
                    parser.restore(backup, destination)
                self.assertEqual(injected, [destination])
                self.assertTrue(destination.exists())
        self.assertEqual(self.source.read_bytes(), self.document.raw)

    def test_actual_destination_readback_rejects_changed_output(self):
        destination = self.folder / 'readback.bin'
        original_write = parser.atomic_new
        injected = []
        def corrupt(data, path):
            result = original_write(data, path)
            if Path(path) == destination:
                injected.append(destination)
                changed = bytearray(data)
                changed[-1] ^= 1
                destination.write_bytes(bytes(changed))
            return result
        with patch.object(parser, 'atomic_new', side_effect=corrupt), self.assertRaises(SaveError):
            parser.save_as(self.document, {'amuro_skill_1': 1}, destination)
        self.assertEqual(injected, [destination])
        self.assertEqual(self.source.read_bytes(), self.document.raw)

    def test_restore_rechecks_opaque_destination_and_backup_companion(self):
        backup = parser.backup(self.document)
        original_restore = parser.restore_snapshot
        for target in ('destination', 'backup'):
            with self.subTest(target=target):
                (self.folder / 'PARAM.SFO').write_bytes(metadata())
                backup.with_suffix('.sfo').write_bytes(metadata())
                destination = self.folder / f'restore-{target}.bin'
                def mutate(*args, **kwargs):
                    path = self.folder / 'PARAM.SFO' if target == 'destination' else backup.with_suffix('.sfo')
                    path.write_bytes(metadata() + b'changed-during-restore')
                    return original_restore(*args, **kwargs)
                with patch.object(parser, 'restore_snapshot', side_effect=mutate), self.assertRaises(SaveError):
                    parser.restore(backup, destination)
                self.assertFalse(destination.exists())
        self.assertEqual(self.source.read_bytes(), self.document.raw)

    def test_restore_checks_exact_backup_identity_and_integrity(self):
        backup = parser.backup(self.document)
        self.assertEqual(backup.with_suffix('.sfo').read_bytes(), metadata())
        for foreign in ('BLES00147-00', 'BLUS30058-02'):
            (self.folder / 'PARAM.SFO').write_bytes(metadata(foreign))
            with self.assertRaises(SaveError):
                parser.restore(backup, self.folder / 'foreign-restore.bin')
        (self.folder / 'PARAM.SFO').write_bytes(metadata())
        backup.with_suffix('.sfo').unlink()
        with self.assertRaises(SaveError):
            parser.restore(backup, self.folder / 'missing-identity.bin')
        self.assertFalse((self.folder / 'foreign-restore.bin').exists())

    def test_optional_genuine_roundtrip_and_every_available_learning_edit(self):
        copies = os.environ.get('GUNDAM1_PS3_COPIES')
        if not copies:
            self.skipTest('No private genuine decrypted Gundam PS3 fixture folder supplied.')
        paths = sorted(Path(copies).glob('*/*/DATA.BIN.decrypted'))
        self.assertTrue(paths)
        count = 0
        for source in paths:
            document = parser.decode(source.read_bytes(), source=source)
            self.assertEqual(parser.serialize(document, {}), document.raw)
            for field in parser.fields_for(document):
                if isinstance(field, parser.EquippedField):
                    continue  # Native equipment dependencies have their own tests.
                if not field.value(document.raw):
                    output = parser.serialize(document, {field.id: 1})
                    self.assertEqual(field.value(output), 1)
                    parser.decode(output, source=source)
                    count += 1
        self.assertGreater(count, 0)

    def test_real_tk_learning_review_undo_max_and_save(self):
        import tkinter as tk
        from koei_editor.games.gundam1_ps3.editor import Editor
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.addCleanup(root.destroy)
        root.withdraw()
        editor = Editor(root)
        with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(self.source)):
            editor.open()
        editor.search.set('Amuro')
        editor.refresh()
        self.assertEqual(len(editor.fields.get_children()), 36)
        editor.fields.selection_set('amuro_skill_1')
        editor.value.set('1')
        editor.apply_selected()
        self.assertEqual(editor.changes, {'amuro_skill_1': 1})
        editor.review()
        editor.undo()
        self.assertEqual(editor.changes, {})
        editor.max_visible()
        self.assertEqual(editor.changes, {})
        editor.stage_values({'amuro_skill_1': 1})
        destination = self.folder / 'gui-edited.bin'
        editor.save_to(destination)
        self.assertEqual(parser.field_map(parser.read_save(destination))['amuro_skill_1'].value(destination.read_bytes()), 1)
        self.assertEqual(self.source.read_bytes(), self.document.raw)
        self.assertTrue(editor.backup.exists())
