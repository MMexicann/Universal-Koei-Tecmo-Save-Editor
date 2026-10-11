"""Procedural format checks and optional genuine decrypted PS4/Tk workflows."""
from dataclasses import replace
import os
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.p5strikers_ps4 import codec, parser
from koei_editor.games.p5strikers_ps4.context import title_only_sfo, title_id
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from tests.scalar_contract import ScalarContractTests


def add_context(folder, raw=None):
    companion = Path(folder) / 'sce_sys' / 'param.sfo'
    companion.parent.mkdir(exist_ok=True)
    companion.write_bytes(raw if raw is not None else title_only_sfo())
    return companion


def fixture():
    """Distinctive procedural bytes; never a playable or genuine save."""
    raw = bytearray(codec.SAVE_SIZE)
    raw[:codec.SLOTS_END] = bytes((i * 29 + 61) % 256 for i in range(codec.SLOTS_END))
    raw[:4] = codec.VERSION_BYTES
    struct.pack_into('<i', raw, 4, 1)
    for slot in range(codec.SLOT_COUNT):
        base = codec.HEADER_SIZE + slot * codec.SLOT_SIZE
        struct.pack_into('<I', raw, base + codec.MARKER_RELATIVE, codec.LAYOUT_MARKER)
        raw[base:base + 2] = b'\xff\xff'
        raw[base + codec.NAME_RELATIVE:base + codec.NAME_RELATIVE + codec.NAME_SIZE * 2] = bytes(codec.NAME_SIZE * 2)
    base = parser._base(1)
    raw[base:base + 2] = b'\x90\x01'
    for relative in (codec.NAME_RELATIVE, codec.NAME_RELATIVE + codec.NAME_SIZE):
        raw[base + relative:base + relative + codec.NAME_SIZE] = b'Generated\0' + bytes(codec.NAME_SIZE - 10)
    for identity, _label, relative, _maximum in parser.RESOURCE_MAP:
        struct.pack_into('<I', raw, base + relative, 37)
    for _group, records in parser.ITEM_GROUPS:
        for relative, _name in records:
            raw[base + relative:base + relative + 2] = b'\x14\0'
    return bytes(raw)


class P5PS4ContractTests(ScalarContractTests, unittest.TestCase):
    game_id = parser.GAME_ID

    def fixture_bytes(self):
        return fixture()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.game = SimpleNamespace(extension='.bin')
        self.adapter = BoundScalarAdapter(parser.GAME_ID, '.bin', parser)
        self.raw = fixture()
        self.source = self.folder / 'savedata-copy.bin'
        self.source.write_bytes(self.raw)
        add_context(self.folder)
        self.document = self.adapter.read_save(self.source)


class P5PS4FormatTests(unittest.TestCase):
    def test_mandatory_title_context_source_destination_restore_and_races(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'APP.BIN'
            source.write_bytes(fixture())
            with self.assertRaises(SaveError):
                parser.read_save(source)
            companion = add_context(folder)
            original_context = companion.read_bytes()
            for bad in (original_context.replace(b'CUSA19640', b'CUSA12153'),
                        original_context[:-1], bytes(4097), b'',
                        original_context[:12] + b'\xff' * 4 + original_context[16:]):
                with self.assertRaises(SaveError):
                    title_id(bad)
            document = parser.read_save(source)
            snapshot = parser.backup(document)
            companion.write_bytes(original_context + b'\0')
            with self.assertRaises(SaveError):
                parser.save_as(document, {}, folder / 'changed.bin')
            with self.assertRaises(SaveError):
                parser.restore(snapshot, folder / 'changed-restore.bin')
            companion.write_bytes(original_context)
            other = folder / 'other'
            other.mkdir()
            add_context(other, original_context + b'\0')
            with self.assertRaises(SaveError):
                parser.save_as(document, {}, other / 'foreign-context.bin')
            with self.assertRaises(SaveError):
                parser.restore(snapshot, other / 'foreign-restore.bin')
            add_context(other, original_context)
            actual = parser.backup
            def change_destination(d):
                result = actual(d)
                add_context(other, original_context + b'\0')
                return result
            with patch.object(parser, 'backup', side_effect=change_destination):
                with self.assertRaises(SaveError):
                    parser.save_as(document, {'slot_1_money': 5}, other / 'race.bin')
            self.assertFalse((other / 'race.bin').exists())
            snapshot.with_name(snapshot.name + '.context.json').unlink()
            with self.assertRaises(SaveError):
                parser.restore(snapshot, folder / 'no-context.bin')
            self.assertFalse((folder / 'no-context.bin').exists())
            with self.assertRaises(SaveError):
                parser.backup(parser.decode(fixture(), source=source))

    def test_every_curated_field_surgical_original_unstage_and_no_max(self):
        raw = fixture()
        document = parser.decode(raw)
        self.assertEqual(parser.serialize(document, {}), raw)
        self.assertGreater(len(parser.fields_for(document)), 90)
        for field in parser.fields_for(document):
            value = field.minimum if field.value(raw) != field.minimum else field.maximum
            pending = parser.stage(document, {}, field.id, value)
            edited = parser.serialize(document, pending)
            self.assertEqual(edited[:field.offset], raw[:field.offset])
            self.assertEqual(edited[field.offset + field.size:], raw[field.offset + field.size:])
            self.assertEqual(field.value(edited), value)
            self.assertEqual(parser.stage(document, pending, field.id, field.value(raw)), {})
            self.assertEqual(parser.maximums(document, pending), pending)
            self.assertEqual(parser.limit_values(document, pending, [field.id]), {})
        self.assertEqual(document.raw, raw)
        self.assertTrue(all(not field.maxable for field in parser.fields_for(document)))

    def test_framing_foreign_platform_language_revision_length_and_tail(self):
        raw = fixture()
        for bad in (raw[:-1], raw + b'\0', bytearray(raw), bytes(len(raw)), raw + bytes(0x55DEA0 - len(raw)), raw + bytes(0x600000 - len(raw))):
            with self.assertRaises(SaveError):
                parser.decode(bad)
        for offset in (0, 4, len(raw) - 1,
                       *(parser._base(slot) + codec.MARKER_RELATIVE for slot in range(10))):
            modified = bytearray(raw)
            if offset == 4:
                struct.pack_into('<I', modified, offset, 10)
            else:
                modified[offset] ^= 1
            with self.assertRaises(SaveError):
                parser.decode(bytes(modified))
        # Japanese PS4 names occupy 13 bytes; its distinct stride is rejected.
        japanese = bytearray(raw)
        for slot in range(10):
            struct.pack_into('<I', japanese, parser._base(slot) + codec.MARKER_RELATIVE, 0)
            struct.pack_into('<I', japanese, 0x1C + slot * (0x88DF4 + 26) + codec.MARKER_RELATIVE, codec.LAYOUT_MARKER)
        with self.assertRaises(SaveError):
            parser.decode(bytes(japanese))
        with self.assertRaises(SaveError):
            parser.decode(raw, 'p5strikers_pc')

    def test_empty_unknown_names_inventory_and_unusual_values_preserved(self):
        raw = bytearray(fixture())
        base = parser._base(1)
        struct.pack_into('<I', raw, base + parser.RESOURCE_MAP[0][2], 0xFFFFFFFF)
        relative = parser.ITEM_GROUPS[0][1][0][0]
        raw[base + relative:base + relative + 2] = b'\xff\x01'
        document = parser.decode(bytes(raw))
        self.assertNotIn(f'slot_1_item_{relative:x}', parser.field_map(document))
        pending = parser.stage(document, {}, 'slot_1_money', 5)
        self.assertEqual(parser.stage(document, pending, 'slot_1_money', 0xFFFFFFFF), {})
        self.assertEqual(parser.maximums(document, {}), {})
        self.assertEqual(parser.serialize(document, {})[base + relative:base + relative + 2], b'\xff\x01')
        self.assertFalse(any(field.slot != 1 for field in parser.fields_for(document)))
        for bad_name in (b'\xff\0', b'Bad\x01\0', b'X' * 33):
            unknown = bytearray(raw)
            unknown[base + codec.NAME_RELATIVE:base + codec.NAME_RELATIVE + 33] = bad_name.ljust(33, b'\0')
            doc = parser.decode(bytes(unknown))
            self.assertEqual(parser.fields_for(doc), ())
            self.assertEqual(parser.serialize(doc, {}), bytes(unknown))

    def test_invalid_types_keys_unknown_mechanics_and_snapshots(self):
        document = parser.decode(fixture())
        for key in ('slot_1_money', 'slot_1_persona_points', 'slot_1_bond_points'):
            for value in (True, '1', 1.0, -1, parser.field_map(document)[key].maximum + 1):
                for operation in (parser.stage,):
                    with self.assertRaises(SaveError):
                        operation(document, {}, key, value)
                with self.assertRaises(SaveError):
                    parser.serialize(document, {key: value})
        for key in ([], 3, None, 'story', 'character_level', 'persona', 'recipe', 'slot_0_money', 'slot_2_money'):
            with self.assertRaises(SaveError):
                parser.stage(document, {}, key, 1)
            with self.assertRaises(SaveError):
                parser.limit_values(document, {}, [key])
        for bad in (replace(document, payload=document.payload[:-1]),
                    replace(document, raw=bytearray(document.raw)),
                    replace(document, format=replace(parser.FORMAT, id='p5strikers_pc'))):
            with self.assertRaises(SaveError):
                parser.serialize(bad, {})

    def test_source_change_backup_race_resolved_alias_and_forged_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'savedata-copy.bin'
            raw = fixture()
            source.write_bytes(raw)
            add_context(folder)
            document = parser.read_save(source)
            snapshot = parser.backup(document)
            source.write_bytes(raw[:-1] + b'\x01')
            with self.assertRaises(SaveError):
                parser.backup(document)
            source.write_bytes(raw)
            actual = parser.backup
            def mutate(d):
                result = actual(d)
                source.write_bytes(raw[:-1] + b'\x01')
                return result
            destination = folder / 'race-copy.bin'
            with patch.object(parser, 'backup', side_effect=mutate):
                with self.assertRaises(SaveError):
                    parser.save_as(document, {'slot_1_money': 50}, destination)
            self.assertFalse(destination.exists())
            source.write_bytes(raw)
            alias = folder / 'alias-copy.bin'
            try:
                alias.symlink_to(source)
            except OSError:
                alias = source
            with self.assertRaises(FileExistsError):
                parser.save_as(document, {}, alias)
            import hashlib, json
            altered = bytearray(raw)
            altered[-1] = 1
            snapshot.write_bytes(altered)
            manifest = json.loads(snapshot.with_suffix('.json').read_text())
            manifest['sha256'] = hashlib.sha256(altered).hexdigest()
            snapshot.with_suffix('.json').write_text(json.dumps(manifest))
            with self.assertRaises(SaveError):
                parser.restore(snapshot, folder / 'forged-copy.bin')
            self.assertFalse((folder / 'forged-copy.bin').exists())
            source.unlink()
            with self.assertRaises(SaveError):
                parser.backup(document)

    def test_genuine_exports_each_field_safe_save_restore_and_self_test(self):
        supplied = os.environ.get('P5S_PS4_SAVE_COPIES')
        if not supplied:
            self.skipTest('Private native English PS4 exports are not configured.')
        from koei_editor.shared.verified_self_test import _run
        paths = [Path(value) for value in supplied.split(os.pathsep)]
        self.assertGreaterEqual(len(paths), 1)
        hashes = set()
        for original in paths:
            raw = original.read_bytes()
            hashes.add(parser.decode(raw).sha256)
            with tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                source = folder / 'savedata-copy.bin'
                source.write_bytes(raw)
                add_context(folder, (original.parent / 'sce_sys' / 'param.sfo').read_bytes())
                doc = parser.read_save(source)
                self.assertGreater(len(parser.fields_for(doc)), 20)
                self.assertEqual(parser.serialize(doc, {}), raw)
                for field in parser.fields_for(doc):
                    value = field.minimum if field.value(raw) != field.minimum else field.maximum
                    result = parser.serialize(doc, {field.id: value})
                    self.assertEqual(result[:field.offset], raw[:field.offset])
                    self.assertEqual(result[field.offset + field.size:], raw[field.offset + field.size:])
                    self.assertEqual(parser.stage(doc, {field.id: value}, field.id, field.value(raw)), {})
                field = parser.fields_for(doc)[0]
                edited = parser.save_as(doc, {field.id: 123}, folder / 'edited-copy.bin')
                self.assertEqual(field.value(edited.payload), 123)
                self.assertEqual(parser.progression_records(doc), parser.progression_records(edited))
                self.assertEqual(parser.restore(parser.backup(doc), folder / 'restored-copy.bin').read_bytes(), raw)
                report = _run(BoundScalarAdapter(parser.GAME_ID, '.bin', parser), parser.GAME_ID,
                              source, folder / 'copied-self-test')
                self.assertTrue(report['success'])
                self.assertFalse(report['native_integrity_verified'])
                self.assertEqual(report['integrity_kind'], 'none')
                self.assertFalse(report['in_game_load_tested'])
                self.assertEqual(source.read_bytes(), raw)
                self.assertEqual(original.read_bytes(), raw)
        self.assertEqual(len(hashes), len(paths))

    def test_actual_tk_named_search_undo_review_and_save(self):
        try:
            import tkinter as tk
            root = tk.Tk()
        except Exception as error:
            self.skipTest('Tk display unavailable: ' + type(error).__name__)
        self.addCleanup(root.destroy)
        from koei_editor.games.p5strikers_ps4.editor import Editor
        selected = os.environ.get('P5S_PS4_SAVE_COPIES')
        raw = Path(selected.split(os.pathsep)[0]).read_bytes() if selected else fixture()
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'savedata-copy.bin'
            source.write_bytes(raw)
            add_context(folder, (Path(selected.split(os.pathsep)[0]).parent / 'sce_sys' / 'param.sfo').read_bytes() if selected else None)
            editor = Editor(root, parent=root)
            with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                editor.open()
            root.update()
            count = len(editor.fields.get_children())
            self.assertGreater(count, 20)
            editor.search.set('Medicine')
            root.update()
            self.assertGreater(len(editor.fields.get_children()), 0)
            self.assertLess(len(editor.fields.get_children()), count)
            editor.search.set('')
            editor.stage_values({'slot_1_money': 123})
            self.assertEqual(editor.changes, {'slot_1_money': 123})
            editor.undo()
            self.assertEqual(editor.changes, {})
            editor.stage_values({'slot_1_money': 123})
            children = set(root.winfo_children())
            editor.review()
            root.update()
            dialogs = [window for window in root.winfo_children()
                       if window not in children and isinstance(window, tk.Toplevel)]
            self.assertEqual(len(dialogs), 1)
            dialogs[0].destroy()
            destination = folder / 'edited-copy.bin'
            with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(destination)):
                editor.save_as()
            doc = parser.read_save(destination)
            self.assertEqual(parser.field_map(doc)['slot_1_money'].value(doc.payload), 123)
            self.assertEqual(source.read_bytes(), raw)
            self.assertTrue(list((folder / 'UniversalEditorBackups').glob('*.json')))
            self.assertEqual(len(editor.presentation.inspection_tables(doc)), 4)


if __name__ == '__main__':
    unittest.main()
