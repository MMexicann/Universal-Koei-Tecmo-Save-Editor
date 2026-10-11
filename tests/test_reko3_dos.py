"""Procedural format checks and optional private original DOS native reference."""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.reko3_dos import parser


def procedural_raw():
    raw = bytearray((i * 17 + 53) & 255 for i in range(parser.SIZE))
    label = '序章 群雄起兵'.encode('cp950')
    raw[5:28] = label + bytes(23 - len(label))
    for index in range(parser.RECORD_COUNT):
        base = parser.RECORD_START + index * parser.RECORD_SIZE
        raw[base:base + 18] = bytes((0x8e, 1, 0, 0, 0, 0, 0, 0, 1, 0, *([255] * 8)))
    for index in (0, 1, 2, 53):
        base = parser.RECORD_START + index * parser.RECORD_SIZE
        raw[base] = 0x80
        raw[base + 4] = 100
        raw[base + 5:base + 7] = (500 + index).to_bytes(2, 'little')
        raw[base + 7] = 6 if index else 0
        raw[base + 9] = 75
    return bytes(raw)


def native_raw():
    selected = os.environ.get('REKO3_DOS_NATIVE_COPY')
    return Path(selected).read_bytes() if selected else procedural_raw()


class LegendLiuBeiTests(unittest.TestCase):
    def setUp(self):
        self.doc = parser.decode(procedural_raw())

    def assert_surgical(self, doc):
        self.assertEqual(parser.serialize(doc, {}), doc.raw)
        self.assertEqual(len(parser.character_records(doc)), 384)
        for field in parser.fields_for(doc):
            value = field.minimum if field.value(doc.raw) != field.minimum else field.maximum
            edited = parser.serialize(doc, {field.id: value})
            expected = bytearray(doc.raw)
            expected[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
            self.assertEqual(edited, bytes(expected))
            self.assertEqual(parser.field_map(parser.decode(edited))[field.id].value(edited), value)
            staged = parser.stage(doc, {}, field.id, value)
            self.assertEqual(parser.stage(doc, staged, field.id, field.value(doc.raw)), {})

    def test_every_field_is_surgical_and_array_tail_is_never_a_character(self):
        self.assert_surgical(self.doc)
        self.assertEqual(len(parser.fields_for(self.doc)), 8)
        fields = parser.field_map(self.doc)
        for key in ('character_3_troops', 'character_384_troops', 'character_0_level', 'character_0_items'):
            self.assertNotIn(key, fields)
            with self.assertRaises(SaveError):
                parser.serialize(self.doc, {key: 1})

    def test_invalid_values_bool_fields_and_pending_mappings_rejected(self):
        for changes in ({'character_0_troops': 0}, {'character_0_troops': 501},
                        {'character_0_exp': -1}, {'character_0_exp': 100},
                        {'character_0_exp': True}, {1: 2}, [], None):
            with self.assertRaises(SaveError):
                parser.serialize(self.doc, changes)
        with self.assertRaises(SaveError):
            parser.stage(self.doc, {}, 'character_3_exp', 1)

    def test_max_preserves_all_values_and_existing_edits(self):
        changes = {'character_0_exp': 99, 'character_0_troops': 123}
        self.assertEqual(parser.maximums(self.doc, changes), changes)
        self.assertEqual(parser.limit_values(self.doc, changes, tuple(parser.field_map(self.doc))), {})
        self.assertTrue(all(not field.maxable for field in parser.fields_for(self.doc)))
        with self.assertRaises(SaveError):
            parser.limit_values(self.doc, {}, ('character_384_exp',))

    def test_unusual_values_are_preserved_and_can_be_unstaged(self):
        raw = bytearray(self.doc.raw)
        raw[parser.RECORD_START + 9] = 255
        raw[parser.RECORD_START + 5:parser.RECORD_START + 7] = b'\xff\xff'
        # Other character records may have opaque/unknown bytes; don't normalize.
        raw[parser.RECORD_START + 18 + 2] = 201
        raw[parser.RECORD_START + 36 + 7] = 99
        doc = parser.decode(raw)
        self.assertEqual(parser.serialize(doc, {}), bytes(raw))
        self.assertNotIn('character_2_exp', parser.field_map(doc))
        staged = parser.stage(doc, {}, 'character_0_exp', 99)
        self.assertEqual(parser.stage(doc, staged, 'character_0_exp', 255), {})
        self.assertEqual(parser.maximums(doc, {}), {})
        self.assertEqual(parser.serialize(doc, {'character_0_exp': 99})[parser.RECORD_START + 5:parser.RECORD_START + 7], b'\xff\xff')

    def test_input_identity_freezing_and_forged_snapshots(self):
        mutable = bytearray(self.doc.raw)
        opened = parser.decode(mutable)
        mutable[100] ^= 255
        self.assertEqual(opened.raw, self.doc.raw)
        for forged in (replace(opened, payload=bytearray(opened.raw)),
                       replace(opened, raw=bytearray(opened.raw)),
                       replace(opened, format=replace(opened.format)),
                       replace(opened, payload=opened.raw[:-1])):
            with self.assertRaises(SaveError):
                parser.serialize(forged, {})
        for raw in (self.doc.raw[:-1], self.doc.raw + b'x', bytes(parser.SIZE), 'not binary'):
            with self.assertRaises(SaveError):
                parser.decode(raw)
        for offset, value in ((parser.RECORD_START, 129), (parser.RECORD_START + 18, 127), (5, 255)):
            raw = bytearray(self.doc.raw)
            raw[offset] = value
            with self.assertRaises(SaveError):
                parser.decode(raw)
        with self.assertRaises(SaveError):
            parser.decode(self.doc.raw, 'reko3_ps1')

    def test_safe_edits_backup_restore_and_existing_destinations(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            source = directory / 'copy.R3S'
            source.write_bytes(self.doc.raw)
            opened = parser.read_save(source)
            edited = parser.save_as(opened, {'character_0_troops': 123}, directory / 'edited.r3s')
            self.assertEqual(parser.field_map(edited)['character_0_troops'].value(edited.raw), 123)
            self.assertEqual(source.read_bytes(), opened.raw)
            backup = parser.backup(opened)
            restored = directory / 'restored.r3s'
            self.assertEqual(parser.restore(backup, restored), restored.resolve())
            self.assertEqual(restored.read_bytes(), opened.raw)
            with self.assertRaises(FileExistsError):
                parser.save_as(opened, {}, edited.source)
            with self.assertRaises(SaveError):
                parser.save_as(opened, {}, directory / 'foreign.dat')
            source.write_bytes(opened.raw[:-1])
            with self.assertRaises(SaveError):
                parser.backup(opened)
            with self.assertRaises(SaveError):
                parser.save_as(opened, {}, directory / 'changed.r3s')

    def test_source_race_after_backup_and_live_game_copy_rejection(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            source = directory / 'copy.r3s'
            source.write_bytes(self.doc.raw)
            opened = parser.read_save(source)
            actual_backup = parser.backup
            def raced(document):
                result = actual_backup(document)
                changed = bytearray(document.raw)
                changed[-1] ^= 255
                source.write_bytes(changed)
                return result
            target = directory / 'changed.r3s'
            with patch.object(parser, 'backup', side_effect=raced), self.assertRaises(SaveError):
                parser.save_as(opened, {}, target)
            self.assertFalse(target.exists())
            source.write_bytes(opened.raw)
            (directory / 'REKO3.EXE').write_bytes(b'procedural marker; never executable')
            with self.assertRaises(SaveError):
                parser.read_save(source)

    @unittest.skipUnless(os.environ.get('REKO3_DOS_NATIVE_COPY'), 'Private original DOS reference not selected')
    def test_native_reference_all_fields_and_owned_record_boundary(self):
        doc = parser.read_save(Path(os.environ['REKO3_DOS_NATIVE_COPY']))
        self.assert_surgical(doc)
        self.assertEqual({field.slot for field in parser.fields_for(doc)}, {0, 1, 2})
        self.assertEqual(len(parser.fields_for(doc)), 6)


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'Graphical display required')
class LegendLiuBeiGuiTests(unittest.TestCase):
    def test_actual_tk_copy_undo_review_inspection_and_save_restore(self):
        import tkinter as tk
        from koei_editor.games.reko3_dos.editor import Editor
        root = tk.Tk()
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as name:
                directory = Path(name)
                source = directory / 'copy.r3s'
                source.write_bytes(native_raw())
                editor = Editor(root)
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)), \
                     patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                    editor.open()
                    errors.assert_not_called()
                self.assertEqual(len(editor.presentation.inspection_tables(editor.document)[0].rows), 384)
                editor.fields.selection_set('character_0_exp')
                editor.value.set('99')
                editor.apply_selected()
                self.assertEqual(editor.changes, {'character_0_exp': 99})
                editor.review()
                next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel)).destroy()
                editor.undo()
                self.assertEqual(editor.changes, {})
                editor.value.set('99')
                editor.apply_selected()
                editor.apply_theme('Dark')
                target, restored = directory / 'edited.r3s', directory / 'restored.r3s'
                with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(target)), \
                     patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                    editor.save_as()
                    errors.assert_not_called()
                self.assertEqual(parser.field_map(parser.read_save(target))['character_0_exp'].value(target.read_bytes()), 99)
                backup = next((directory / 'WarriorsEditorBackups').glob('*.r3s'))
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(backup)), \
                     patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(restored)), \
                     patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                    editor.restore()
                    errors.assert_not_called()
                self.assertEqual(restored.read_bytes(), source.read_bytes())
        finally:
            root.destroy()
