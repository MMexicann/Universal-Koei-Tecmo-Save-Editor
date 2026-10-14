"""Separately qualified Switch CMNDAT: procedural, native and actual Tk checks."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zlib

from koei_editor.games.dqb2_pc import parser as pc
from koei_editor.games.dqb2_switch import parser
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from tests.scalar_contract import ScalarContractTests
from tests.test_dqb2_pc import fixture as pc_fixture


def fixture():
    """Generated Switch-profile bytes, not independently native player evidence."""
    return pc_fixture(padded=True, revision=4)


def native_paths():
    setting = os.environ.get('DQB2_SWITCH_SAVE_COPIES', '')
    return [path for entry in setting.split(os.pathsep) if entry
            for path in ([Path(entry)] if Path(entry).is_file() else Path(entry).rglob('CMNDAT.BIN'))]


class Dqb2SwitchContractTests(ScalarContractTests, unittest.TestCase):
    game_id = parser.GAME_ID

    def fixture_bytes(self):
        return fixture()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.game = SimpleNamespace(extension=parser.EXTENSION)
        self.adapter = BoundScalarAdapter(parser.GAME_ID, parser.EXTENSION, parser)
        self.raw = fixture()
        self.source = self.folder / 'CMNDAT.BIN'
        self.source.write_bytes(self.raw)
        self.document = self.adapter.read_save(self.source)


class Dqb2SwitchFormatTests(unittest.TestCase):
    def test_separate_document_format_platform_game_identity(self):
        raw = fixture()
        document = parser.decode(raw)
        self.assertIs(document.format, parser.FORMAT)
        self.assertEqual(document.format.id, 'dqb2_switch')
        pc_document = pc.decode(raw)
        self.assertEqual(pc_document.payload, document.payload)
        for operation in (lambda: parser.fields_for(pc_document),
                          lambda: parser.serialize(pc_document, {}),
                          lambda: pc.fields_for(document),
                          lambda: pc.serialize(document, {}),
                          lambda: parser.decode(raw, 'dqb2_pc'),
                          lambda: parser.get_format('dqb1_switch')):
            with self.assertRaises(SaveError):
                operation()
        self.assertEqual(parser.serialize(document, {}), raw)

    def test_native_noop_and_selected_bulk_changes_are_quantity_only(self):
        document = parser.decode(fixture())
        self.assertEqual(len(parser.item_records(document)), 435)
        self.assertEqual(len(parser.player_records(document)), 11)
        fields = parser.fields_for(document)
        self.assertEqual(len(fields), 435)
        for changes in ({fields[0].id: 3}, {field.id: 1 for field in fields}):
            output = parser.serialize(document, changes)
            reopened = parser.decode(output)
            self.assertEqual(len(output), len(document.raw))
            self.assertEqual(reopened.payload, parser.changed_payload(document, changes))
            changed_fields = [field for field in fields if field.id in changes]
            allowed = {i for field in changed_fields for i in range(field.offset, field.offset + field.size)}
            touched = {i for i, (a, b) in enumerate(zip(document.payload, reopened.payload)) if a != b}
            self.assertTrue(touched)
            self.assertLessEqual(touched, allowed)
            self.assertEqual(parser.player_records(document), parser.player_records(reopened))
            original_used = struct.unpack_from('<I', document.raw, 0x10)[0]
            self.assertEqual(document.raw[original_used:], output[original_used:])
            self.assertEqual(document.raw[:0x10], output[:0x10])
            self.assertEqual(document.raw[0x14:parser.HEADER_SIZE], output[0x14:parser.HEADER_SIZE])
            for field in changed_fields:
                self.assertEqual(field.value(reopened.payload), changes[field.id])

    def test_unsupported_compact_old_revision_broken_adler_extent_and_zlib_bombs_rejected(self):
        raw = fixture()
        old = pc_fixture(padded=True, revision=3)
        compact = pc_fixture(padded=False, revision=4)
        bad_adler = bytearray(raw)
        used = struct.unpack_from('<I', raw, 0x10)[0]
        bad_adler[used - 1] ^= 1
        for bad in (old, compact, raw[:-1], raw + b'\0', bytearray(raw), memoryview(raw), bytes(bad_adler)):
            with self.assertRaises(SaveError):
                parser.decode(bad)
        for value in (0, parser.HEADER_SIZE, len(raw) + 1, 0xFFFFFFFF):
            damaged = bytearray(raw)
            struct.pack_into('<I', damaged, 0x10, value)
            with self.assertRaises(SaveError):
                parser.decode(bytes(damaged))
        for size in (parser.BODY_SIZE - 1, parser.BODY_SIZE + 1, parser.BODY_SIZE * 2):
            stream = zlib.compress(bytes(size))
            damaged = bytearray(raw)
            damaged[parser.HEADER_SIZE:parser.HEADER_SIZE + len(stream)] = stream
            struct.pack_into('<I', damaged, 0x10, parser.HEADER_SIZE + len(stream))
            with self.assertRaises(SaveError):
                parser.decode(bytes(damaged))
        stream = raw[parser.HEADER_SIZE:used] + zlib.compress(b'second member')
        damaged = bytearray(raw)
        damaged[parser.HEADER_SIZE:parser.HEADER_SIZE + len(stream)] = stream
        struct.pack_into('<I', damaged, 0x10, parser.HEADER_SIZE + len(stream))
        with self.assertRaises(SaveError):
            parser.decode(bytes(damaged))

    def test_unusual_unknown_single_empty_and_equipped_records_stay_read_only(self):
        original = parser.decode(fixture())
        body = bytearray(original.payload)
        examples = ((0, 99), (65535, 20), (2, 0), (2, 1), (2, 1000), (2, 65535))
        for index, (item_id, count) in enumerate(examples):
            struct.pack_into('<HH', body, pc.BAG_BASE + index * 4, item_id, count)
        stream = zlib.compress(body, 1)
        raw = bytearray(original.raw)
        raw[parser.HEADER_SIZE:parser.HEADER_SIZE + len(stream)] = stream
        struct.pack_into('<I', raw, 0x10, parser.HEADER_SIZE + len(stream))
        document = parser.decode(bytes(raw))
        for index in range(3):
            self.assertNotIn(f'bag_{index + 1}', parser.field_map(document))
            with self.assertRaises(SaveError):
                parser.stage(document, {}, f'bag_{index + 1}', 1)
        for index in range(3, 6):
            field = parser.field_map(document)[f'bag_{index + 1}']
            self.assertEqual(field.value(document.payload), examples[index][1])
            self.assertEqual(parser.stage(document, {}, field.id, examples[index][1]), {})
        changed = parser.decode(parser.serialize(document, {'pockets_1': 3}))
        self.assertEqual(changed.payload[pc.BAG_BASE:pc.BAG_BASE + 24], document.payload[pc.BAG_BASE:pc.BAG_BASE + 24])
        self.assertEqual(parser.player_records(changed), parser.player_records(document))

    def test_invalid_stage_values_unknown_keys_forged_snapshots_and_max(self):
        document = parser.decode(fixture())
        for value in (0, -1, 11, 999, True, 3.0, '3', None):
            with self.assertRaises(SaveError):
                parser.stage(document, {}, 'pockets_1', value)
            with self.assertRaises(SaveError):
                parser.serialize(document, {'pockets_1': value})
        for key in ('level', 'hp', 'equipment', 'story', 'gratitude', 'bag_421', [], None):
            with self.assertRaises(SaveError):
                parser.stage(document, {}, key, 1)
        for forged in (replace(document, raw=bytearray(document.raw)),
                       replace(document, payload=bytearray(document.payload)),
                       replace(document, payload=document.payload[:-1] + b'\x01'),
                       replace(document, format=replace(document.format, id='dqb2_pc'))):
            with self.assertRaises(SaveError):
                parser.serialize(forged, {})
        pending = parser.stage(document, {}, 'pockets_1', 3)
        self.assertEqual(parser.stage(document, pending, 'pockets_1', 10), {})
        self.assertEqual(parser.maximums(document, pending), pending)
        self.assertEqual(parser.limit_values(document, pending, ['pockets_1']), {})
        with self.assertRaises(SaveError):
            parser.limit_values(document, {}, [[]])

    def test_switch_and_pc_backup_manifests_cannot_be_interchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'CMNDAT.BIN'
            raw = fixture()
            source.write_bytes(raw)
            document = parser.read_save(source)
            snapshot = parser.backup(document)
            metadata = json.loads(snapshot.with_suffix('.json').read_bytes())
            self.assertEqual(metadata['game_id'], 'dqb2_switch')
            with self.assertRaises(SaveError):
                pc.restore(snapshot, folder / 'invalid-pc.bin')
            pc_snapshot = pc.backup(pc.read_save(source))
            with self.assertRaises(SaveError):
                parser.restore(pc_snapshot, folder / 'invalid-switch.bin')
            self.assertEqual(parser.restore(snapshot, folder / 'restored.bin').read_bytes(), raw)
            self.assertFalse((folder / 'invalid-pc.bin').exists())
            self.assertFalse((folder / 'invalid-switch.bin').exists())

    def test_source_unchanged_existing_destination_live_folder_and_symlink_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'CMNDAT.BIN'
            raw = fixture()
            source.write_bytes(raw)
            document = parser.read_save(source)
            output = folder / 'edited.bin'
            saved = parser.save_as(document, {'pockets_1': 3}, output)
            self.assertEqual(parser.field_map(saved)['pockets_1'].value(saved.payload), 3)
            with self.assertRaises(FileExistsError):
                parser.save_as(document, {}, source)
            with self.assertRaises(FileExistsError):
                parser.save_as(document, {}, output)
            live = folder / 'Documents' / 'My Games' / 'DRAGON QUEST BUILDERS II' / 'Steam' / 'CMNDAT.BIN'
            live.parent.mkdir(parents=True)
            live.write_bytes(raw)
            for operation in (lambda: parser.read_save(live),
                              lambda: parser.save_as(document, {}, live.parent / 'new.bin')):
                with self.assertRaises(SaveError):
                    operation()
            alias = folder / 'alias.bin'
            try:
                alias.symlink_to(live)
            except OSError:
                pass
            else:
                with self.assertRaises(SaveError):
                    parser.read_save(alias)
            source.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
            with self.assertRaises(SaveError):
                parser.save_as(document, {}, folder / 'source-changed.bin')
            self.assertFalse((folder / 'source-changed.bin').exists())

    def test_native_two_distinct_slots_noops_surgical_edits_and_safe_storage(self):
        paths = native_paths()
        if not paths:
            self.skipTest('No private genuine extracted Switch CMNDAT copies supplied.')
        seen = set()
        edited_count = 0
        for original in paths:
            raw = original.read_bytes()
            if hashlib.sha256(raw).hexdigest() in seen:
                continue
            seen.add(hashlib.sha256(raw).hexdigest())
            with self.subTest(sample=original.name), tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                source = folder / 'CMNDAT.BIN'
                source.write_bytes(raw)
                document = parser.read_save(source)
                self.assertEqual(parser.serialize(document, {}), raw)
                fields = parser.fields_for(document)
                changes = {field.id: 1 for field in fields}
                output = parser.serialize(document, changes)
                reopened = parser.decode(output)
                allowed = {i for field in fields for i in range(field.offset, field.offset + field.size)}
                touched = {i for i, (a, b) in enumerate(zip(document.payload, reopened.payload)) if a != b}
                self.assertEqual(bool(touched), bool(changes))
                self.assertLessEqual(touched, allowed)
                self.assertEqual(parser.player_records(reopened), parser.player_records(document))
                used = struct.unpack_from('<I', raw, 0x10)[0]
                self.assertEqual(output[used:], raw[used:])
                self.assertEqual(output[:0x10], raw[:0x10])
                self.assertEqual(output[0x14:parser.HEADER_SIZE], raw[0x14:parser.HEADER_SIZE])
                if changes:
                    saved = parser.save_as(document, changes, folder / 'edited.bin')
                    self.assertEqual(saved.payload, reopened.payload)
                    edited_count += 1
                snapshot = parser.backup(document)
                self.assertEqual(parser.restore(snapshot, folder / 'restored.bin').read_bytes(), raw)
                self.assertEqual(source.read_bytes(), raw)
                self.assertEqual(original.read_bytes(), raw)
        self.assertGreater(edited_count, 0)

    def test_actual_tk_native_when_available_search_undo_review_save_as_restore(self):
        try:
            import tkinter as tk
            root = tk.Tk()
        except Exception as error:
            self.skipTest('Tk display unavailable: ' + type(error).__name__)
        self.addCleanup(root.destroy)
        from koei_editor.games.dqb2_switch.editor import Editor
        paths = native_paths()
        raw = next((p.read_bytes() for p in paths if parser.fields_for(parser.decode(p.read_bytes()))), fixture())
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'CMNDAT.BIN'
            source.write_bytes(raw)
            fields = parser.fields_for(parser.decode(raw))
            selected = fields[0]
            editor = Editor(root, parent=root)
            with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                editor.open()
            root.update()
            self.assertEqual(len(editor.fields.get_children()), len(fields))
            editor.search.set(selected.label.removesuffix(' quantity'))
            root.update()
            self.assertIn(selected.id, editor.fields.get_children())
            editor.search.set('')
            pending = {selected.id: min(3, selected.maximum - 1)}
            editor.stage_values(pending)
            self.assertEqual(len(parser.review(editor.document, editor.changes)), 1)
            editor.undo()
            self.assertEqual(editor.changes, {})
            editor.stage_values(pending)
            children = set(root.winfo_children())
            editor.review()
            root.update()
            dialogs = [x for x in root.winfo_children() if x not in children and isinstance(x, tk.Toplevel)]
            self.assertEqual(len(dialogs), 1)
            dialogs[0].destroy()
            destination = folder / 'edited.bin'
            with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(destination)):
                editor.save_as()
            saved = parser.read_save(destination)
            self.assertEqual(selected.value(saved.payload), pending[selected.id])
            self.assertEqual(source.read_bytes(), raw)
            snapshots = [p for p in (folder / 'UniversalEditorBackups').iterdir() if p.suffix.lower() == '.bin']
            self.assertTrue(snapshots)
            self.assertEqual(parser.restore(snapshots[0], folder / 'restored.bin').read_bytes(), raw)


if __name__ == '__main__':
    unittest.main()
