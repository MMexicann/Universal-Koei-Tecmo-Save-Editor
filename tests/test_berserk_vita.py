"""Generated and optional native Vita checks; no game/editor executable is run."""
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

from koei_editor.games.berserk_vita import parser
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from tests.scalar_contract import ScalarContractTests


def metadata(title=parser.TITLE_ID, extra=b''):
    key = b'PARENT_DIRECTORY\0'
    value = ('/' + title).encode('ascii') + b'\0'
    return (struct.pack('<5I', 0x46535000, 0x101, 36, 36 + len(key), 1)
            + struct.pack('<HH3I', 0, 0x204, len(value), len(value), 0) + key + value + extra)


def fixture():
    """Distinctive procedural bytes, not a playable or independently native save."""
    raw = bytearray((i * 47 + 29) % 256 for i in range(parser.SAVE_SIZE))
    raw[:32] = parser.HEADER
    raw[0x44:0x4C] = bytes(range(8))
    raw[0x54:0x5C] = bytes(range(8))
    struct.pack_into('<I', raw, parser.GOLD_OFFSET, 234567)
    raw[parser.MATERIAL_BASE:parser.MATERIAL_BASE + 18] = bytes(range(1, 19))
    for index in range(8):
        struct.pack_into('<I5H', raw, parser.CHARACTER_BASE + index * parser.CHARACTER_STRIDE,
                         10000 + index, 5000, 200, 150, 120, 80)
    return bytes(raw)


def write_context(folder, raw=None):
    path = Path(folder) / 'sce_sys' / 'param.sfo'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(metadata() if raw is None else raw)
    return path


class BerserkVitaContractTests(ScalarContractTests, unittest.TestCase):
    game_id = parser.GAME_ID

    def fixture_bytes(self):
        return fixture()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.adapter = BoundScalarAdapter(parser.GAME_ID, '.dat', parser)
        self.game = SimpleNamespace(extension='.dat')
        self.raw = fixture()
        self.source = self.folder / 'app0000.dat'
        self.source.write_bytes(self.raw)
        write_context(self.folder)
        self.document = self.adapter.read_save(self.source)


class BerserkVitaFormatTests(unittest.TestCase):
    def test_all_fields_surgical_inventory_and_status_preserved(self):
        raw = fixture()
        doc = parser.decode(raw)
        self.assertEqual(parser.serialize(doc, {}), raw)
        self.assertEqual(len(parser.fields_for(doc)), 19)
        for field in parser.fields_for(doc):
            original = field.value(raw)
            value = field.minimum if original != field.minimum else field.maximum
            pending = parser.stage(doc, {}, field.id, value)
            output = parser.serialize(doc, pending)
            self.assertEqual(output[:field.offset], raw[:field.offset])
            self.assertEqual(output[field.offset + field.size:], raw[field.offset + field.size:])
            self.assertEqual(field.value(output), value)
            self.assertEqual(parser.stage(doc, pending, field.id, original), {})
            self.assertEqual(parser.maximums(doc, pending), pending)
            self.assertEqual(parser.limit_values(doc, pending, [field.id]), {})
        self.assertEqual(len(parser.material_records(doc)), 18)
        self.assertEqual(parser.character_records(doc)[0], ('Guts', 10000, 5000, 200, 150, 120, 80))
        self.assertEqual(parser.character_records(doc)[4][0], 'Character slot 5')
        self.assertEqual(parser.record_label(7), 'Ruby')

    def test_zero_sentinel_and_unusual_materials_not_activated_or_normalized(self):
        raw = bytearray(fixture())
        raw[parser.MATERIAL_BASE:parser.MATERIAL_BASE + 4] = bytes((0, 100, 255, 99))
        struct.pack_into('<I', raw, parser.GOLD_OFFSET, 0xFFFFFFFF)
        doc = parser.decode(bytes(raw))
        mapping = parser.field_map(doc)
        for index in range(3):
            self.assertNotIn(f'material_{index}', mapping)
            with self.assertRaises(SaveError):
                parser.stage(doc, {}, f'material_{index}', 1)
        self.assertEqual(parser.serialize(doc, {}), bytes(raw))
        self.assertEqual(parser.maximums(doc, {}), {})
        pending = parser.stage(doc, {}, 'gold', 10)
        self.assertEqual(parser.stage(doc, pending, 'gold', 0xFFFFFFFF), {})
        self.assertEqual(parser.serialize(doc, pending)[parser.MATERIAL_BASE:parser.MATERIAL_BASE + 4], bytes((0, 100, 255, 99)))

    def test_invalid_values_unknown_and_dependent_fields_rejected(self):
        doc = parser.decode(fixture())
        for key, values in [('gold', (-1, 234568, True, '4', 2.0)),
                            ('material_0', (-1, 100, 255, True, '1', 2.0))]:
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(SaveError):
                    parser.stage(doc, {}, key, value)
                with self.assertRaises(SaveError):
                    parser.serialize(doc, {key: value})
        for key in ('character_0_exp', 'character_0_attack', 'level', 'story_complete',
                    'horse', 'accessory', 'behelits', 'unknown_stat', 'lifetime_gold'):
            with self.assertRaises(SaveError):
                parser.serialize(doc, {key: 1})
        with self.assertRaises(SaveError):
            parser.review(doc, {'gold': True})
        with self.assertRaises(SaveError):
            parser.maximums(doc, {'gold': True})
        with self.assertRaises(SaveError):
            parser.serialize(replace(doc, context_sha256='not-a-digest'), {})

    def test_complete_profile_and_foreign_or_malformed_metadata_rejected(self):
        raw = fixture()
        for bad in (raw[:-1], raw + b'\0', bytearray(raw), b'\0' * len(raw)):
            with self.assertRaises(SaveError):
                parser.decode(bad)
        for offset in (4, 8, 24, 0x44, 0x54):
            bad = bytearray(raw)
            bad[offset] ^= 1
            with self.assertRaises(SaveError):
                parser.decode(bytes(bad))
        good = metadata()
        self.assertEqual(parser.parent_directory(good), '/PCSB01085')
        for bad in (metadata('PCSE01034'), metadata('PCSE00296'), good[:-1],
                    good + b'\0' * 4096, b'\0' * 64, bytearray(good)):
            with self.assertRaises(SaveError):
                parser.parent_directory(bad)
        for offset, value in ((4, 0x102), (8, 0xFFFFFFFF), (12, 0), (16, 129),
                              (24, 0xFFFFFFFF), (28, 0xFFFFFFFF), (32, 0xFFFFFFFF)):
            bad = bytearray(good)
            struct.pack_into('<I', bad, offset, value)
            with self.assertRaises(SaveError):
                parser.parent_directory(bytes(bad))

    def test_source_destination_context_and_forged_restore_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'app0000.dat'
            source.write_bytes(fixture())
            with self.assertRaises(SaveError):
                parser.read_save(source)
            companion = write_context(folder)
            doc = parser.read_save(source)
            saved = parser.save_as(doc, {'gold': 123, 'material_0': 99}, folder / 'edited.dat')
            self.assertEqual(parser.field_map(saved)['gold'].value(saved.raw), 123)
            self.assertEqual(source.read_bytes(), fixture())
            snapshot = parser.backup(doc)
            self.assertEqual(parser.restore(snapshot, folder / 'restored.dat').read_bytes(), fixture())
            other = folder / 'other'
            other.mkdir()
            write_context(other, metadata(extra=b'different context'))
            for action in (lambda: parser.save_as(doc, {}, other / 'edited.dat'),
                           lambda: parser.restore(snapshot, other / 'restored.dat')):
                with self.assertRaises(SaveError):
                    action()
            self.assertFalse((other / 'edited.dat').exists())
            self.assertFalse((other / 'restored.dat').exists())
            companion.write_bytes(metadata(extra=b'changed'))
            for action in (lambda: parser.backup(doc),
                           lambda: parser.save_as(doc, {}, folder / 'changed.dat')):
                with self.assertRaises(SaveError):
                    action()
            companion.write_bytes(metadata())
            forged = bytearray(fixture())
            forged[0x44] ^= 1
            snapshot.write_bytes(forged)
            manifest = json.loads(snapshot.with_suffix('.json').read_text())
            manifest['sha256'] = hashlib.sha256(forged).hexdigest()
            snapshot.with_suffix('.json').write_text(json.dumps(manifest))
            with self.assertRaises(SaveError):
                parser.restore(snapshot, folder / 'forged.dat')
            self.assertFalse((folder / 'forged.dat').exists())

    def test_self_test_context_is_title_only_and_unqualified_memory_cannot_write(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            doc = parser.decode(fixture())
            output = folder / 'self-test' / 'app0000.dat'
            parser.prepare_self_test_copy(doc, output)
            sfo = (output.parent / 'sce_sys' / 'param.sfo').read_bytes()
            self.assertEqual(parser.parent_directory(sfo), '/PCSB01085')
            self.assertEqual(struct.unpack_from('<I', sfo, 16)[0], 1)
            self.assertNotIn(b'ACCOUNT', sfo)
            self.assertNotIn(b'PARAMS', sfo)
            with self.assertRaises(SaveError):
                parser.backup(doc)

    def test_optional_genuine_corpus_all_fields_surgical_safe_save(self):
        selected = os.environ.get('BERSERK_VITA_NATIVE_DIR')
        if not selected:
            self.skipTest('No private complete decrypted EU Vita corpus provided.')
        paths = sorted(Path(selected).rglob('app*.dat'))
        self.assertGreaterEqual(len(paths), 2)
        for original in paths:
            raw = original.read_bytes()
            sfo = (original.parent / 'sce_sys' / 'param.sfo').read_bytes()
            self.assertEqual(parser.parent_directory(sfo), '/PCSB01085')
            with tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                source = folder / 'app0000.dat'
                source.write_bytes(raw)
                write_context(folder, sfo)
                doc = parser.read_save(source)
                self.assertEqual(parser.serialize(doc, {}), raw)
                self.assertEqual(len(parser.fields_for(doc)), 19)
                for field in parser.fields_for(doc):
                    value = 0 if field.value(raw) else field.maximum
                    output = parser.serialize(doc, {field.id: value})
                    self.assertEqual(output[:field.offset], raw[:field.offset])
                    self.assertEqual(output[field.offset + field.size:], raw[field.offset + field.size:])
                saved = parser.save_as(doc, {'gold': 10000, 'material_0': 20}, folder / 'edited.dat')
                self.assertEqual(parser.read_save(saved.source).raw, saved.raw)
                self.assertEqual(parser.character_records(saved), parser.character_records(doc))
                snapshot = parser.backup(doc)
                self.assertEqual(parser.restore(snapshot, folder / 'restored.dat').read_bytes(), raw)
                self.assertEqual(source.read_bytes(), raw)
                self.assertEqual(original.read_bytes(), raw)

    def test_actual_tk_search_named_controls_undo_review_and_save(self):
        try:
            import tkinter as tk
            root = tk.Tk()
        except Exception as error:
            self.skipTest('Tk display unavailable: ' + type(error).__name__)
        self.addCleanup(root.destroy)
        from koei_editor.games.berserk_vita.editor import Editor
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'app0000.dat'
            native = os.environ.get('BERSERK_VITA_NATIVE_DIR')
            if native:
                original = next(Path(native).rglob('app*.dat'))
                raw = original.read_bytes()
                sfo = (original.parent / 'sce_sys' / 'param.sfo').read_bytes()
            else:
                raw, sfo = fixture(), metadata()
            source.write_bytes(raw)
            write_context(folder, sfo)
            editor = Editor(root, parent=root)
            with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                editor.open()
            root.update()
            self.assertEqual(len(editor.fields.get_children()), 19)
            editor.search.set('Ruby')
            root.update()
            self.assertEqual(len(editor.fields.get_children()), 2)
            editor.search.set('')
            editor.stage_values({'gold': 123, 'material_0': 20})
            self.assertEqual(len(parser.review(editor.document, editor.changes)), 2)
            editor.undo()
            self.assertEqual(editor.changes, {})
            editor.stage_values({'gold': 123, 'material_0': 20})
            before = set(root.winfo_children())
            editor.review()
            root.update()
            dialogs = [x for x in root.winfo_children() if x not in before and isinstance(x, tk.Toplevel)]
            self.assertEqual(len(dialogs), 1)
            dialogs[0].destroy()
            destination = folder / 'edited.dat'
            with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(destination)):
                editor.save_as()
            self.assertEqual(parser.field_map(parser.read_save(destination))['gold'].value(destination.read_bytes()), 123)
            self.assertEqual(source.read_bytes(), raw)
            self.assertTrue(list((folder / 'UniversalEditorBackups').glob('*.json')))


if __name__ == '__main__':
    unittest.main()
