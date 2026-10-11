"""Procedural occupied campaigns; optional original initialized DOS reference."""
from dataclasses import replace
from functools import lru_cache
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.uncharted_waters2_dos import parser


@lru_cache(maxsize=1)
def procedural_raw():
    raw = bytearray((i * 13 + 29) & 255 for i in range(parser.SIZE))
    raw[:parser.HEADER_SIZE] = bytes(parser.HEADER_SIZE)
    for slot in range(parser.SLOT_COUNT):
        base = parser.HEADER_SIZE + slot * parser.SLOT_SIZE
        for sailor in range(6):
            record = base + parser.SAILOR_START + sailor * parser.SAILOR_SIZE
            raw[record:record + 18] = bytes(18)
            name, surname = (b'Joao', b'Franco') if sailor == 0 else (b'Sailor', str(sailor).encode())
            raw[record:record + len(name)] = name
            raw[record + 9:record + 9 + len(surname)] = surname
            struct.pack_into('<H', raw, record + 18, sailor)
            raw[record + 20:record + 30] = bytes((70, 71, 72, 73, 74, 75, 76, 77, 5, 6))
        raw[base + parser.PORT_START + 4:base + parser.PORT_START + 11] = b'Lisbon\0'
        raw[base + 6:base + 11] = bytes((21, 4, 16, 24, 0))
        struct.pack_into('<I', raw, base + 0x60a, 123456 + slot)
        if slot in (0, 2):
            header = 1 + slot * 15
            raw[header:header + 12] = b'May/17/1522\0'
            raw[header + 13] = slot
    return bytes(raw)


class NewHorizonsDosTests(unittest.TestCase):
    def setUp(self):
        self.doc = parser.decode(procedural_raw())

    def test_roundtrip_and_surgical_gold_attributes_in_multiple_occupied_slots(self):
        self.assertEqual(parser.serialize(self.doc, {}), self.doc.raw)
        self.assertTrue(self.doc.format.published_format)
        self.assertFalse(self.doc.format.sample_verified)
        self.assertFalse(self.doc.format.editing_verified)
        self.assertFalse(self.doc.format.game_load_verified)
        fields = parser.fields_for(self.doc)
        self.assertEqual(len(fields), 18)
        changes = {field.id: field.maximum for field in fields}
        edited = parser.decode(parser.serialize(self.doc, changes))
        allowed = {field.offset + i for field in fields for i in range(field.size)}
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(self.doc.raw, edited.raw))))
        self.assertEqual(len(parser.review(self.doc, changes)), 18)
        for field in fields:
            self.assertEqual(field.value(edited.payload), field.maximum)
            self.assertEqual(parser.stage(self.doc, {field.id: 0}, field.id, field.value(self.doc.payload)), {})
        self.assertEqual(parser.slot_records(self.doc)[1][1], 'Empty')
        self.assertEqual(len(parser.sailor_records(self.doc)), 12)

    def test_invalid_values_foreign_fields_and_unoccupied_slots_reject(self):
        key = parser.fields_for(self.doc)[0].id
        for changes in ({key: -1}, {key: parser.GOLD_MAX + 1}, {key: True},
                        {'slot_1_gold': 1}, {'slot_0_rank': 1}, {'slot_0_attribute_0': 101}, [], None):
            with self.assertRaises(SaveError):
                parser.serialize(self.doc, changes)
        for forged in (replace(self.doc, payload=bytearray(self.doc.payload)),
                       replace(self.doc, raw=bytearray(self.doc.raw)),
                       replace(self.doc, format=replace(self.doc.format))):
            with self.assertRaises(SaveError):
                parser.serialize(forged, {})

    def test_high_originals_and_max_preserve_higher_gold_and_attributes(self):
        raw = bytearray(procedural_raw())
        fields = parser.fields_for(self.doc)
        struct.pack_into('<I', raw, fields[0].offset, 0xffffffff)
        raw[fields[1].offset] = 255
        doc = parser.decode(raw)
        maximums = parser.maximums(doc, {})
        self.assertNotIn(fields[0].id, maximums)
        self.assertNotIn(fields[1].id, maximums)
        self.assertEqual(parser.serialize(doc, {}), bytes(raw))
        for field in fields[:2]:
            staged = parser.stage(doc, {}, field.id, 0)
            self.assertEqual(parser.stage(doc, staged, field.id, field.value(doc.payload)), {})
        self.assertEqual(parser.limit_values(doc, {}, (fields[0].id, fields[1].id)), {})

    def test_empty_reference_layout_has_no_writable_records(self):
        raw = bytearray(procedural_raw())
        raw[:parser.HEADER_SIZE] = bytes(parser.HEADER_SIZE)
        doc = parser.decode(raw)
        self.assertEqual(parser.fields_for(doc), ())
        self.assertEqual(parser.maximums(doc, {}), {})
        self.assertEqual(parser.serialize(doc, {}), bytes(raw))

    def test_title_locale_size_record_ids_slot_label_and_calendar_validation(self):
        for raw in (self.doc.raw[:-1], self.doc.raw + b'x', bytes(parser.SIZE)):
            with self.assertRaises(SaveError):
                parser.decode(raw)
        base = parser.HEADER_SIZE
        for offset, value in ((base + parser.SAILOR_START, b'X'),
                              (base + parser.PORT_START + 4, b'X'),
                              (base + parser.SAILOR_START + 18, b'\xff'),
                              (1, b'X'), (14, b'\x06'), (base + 7, b'\x0c'),
                              (base + 8, b'\x1f'), (base + 9, b'\x48'),
                              (base + 10, b'\x82')):
            raw = bytearray(self.doc.raw)
            raw[offset:offset + len(value)] = value
            with self.assertRaises(SaveError):
                parser.decode(raw)
        with self.assertRaises(SaveError):
            parser.decode(self.doc.raw, 'uncharted_waters2_snes')

    def test_save_as_backups_restoration_existing_destinations_and_changed_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source, target, restored = (directory / name for name in ('copy.dat', 'edited.dat', 'restored.dat'))
            source.write_bytes(self.doc.raw)
            doc = parser.read_save(source)
            key = parser.fields_for(doc)[0].id
            edited = parser.save_as(doc, {key: 987}, target)
            self.assertEqual(parser.field_map(edited)[key].value(edited.payload), 987)
            self.assertEqual(source.read_bytes(), doc.raw)
            backup = parser.backup(doc)
            parser.restore(backup, restored)
            self.assertEqual(restored.read_bytes(), doc.raw)
            with self.assertRaises(FileExistsError):
                parser.save_as(doc, {}, target)
            source.write_bytes(doc.raw[:-1])
            with self.assertRaises(SaveError):
                parser.backup(doc)
            with self.assertRaises(SaveError):
                parser.save_as(doc, {}, directory / 'changed.dat')
            self.assertFalse((directory / 'changed.dat').exists())

    def test_final_source_check_and_live_game_directory_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / 'copy.dat'
            source.write_bytes(self.doc.raw)
            doc = parser.read_save(source)
            real_backup = parser.backup
            def changed_after_backup(document):
                result = real_backup(document)
                source.write_bytes(document.raw[:-1])
                return result
            with patch.object(parser, 'backup', side_effect=changed_after_backup), self.assertRaises(SaveError):
                parser.save_as(doc, {}, directory / 'changed.dat')
            self.assertFalse((directory / 'changed.dat').exists())
            source.write_bytes(doc.raw)
            (directory / 'MAIN.EXE').write_bytes(b'dummy marker; never executed')
            (directory / 'MENU.DAT').write_bytes(b'dummy marker')
            with self.assertRaises(SaveError):
                parser.read_save(source)

    @unittest.skipUnless(os.environ.get('UW2_DOS_REFERENCE_COPY'), 'Original initialized reference not selected')
    def test_native_initialized_reference_is_not_player_save_qualification(self):
        doc = parser.read_save(Path(os.environ['UW2_DOS_REFERENCE_COPY']))
        self.assertEqual(parser.serialize(doc, {}), doc.raw)
        self.assertEqual(parser.fields_for(doc), ())
        self.assertFalse(doc.format.sample_verified)
        self.assertFalse(doc.format.editing_verified)
        self.assertEqual(len(parser.slot_records(doc)), 10)


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'Graphical display required')
class NewHorizonsDosGuiTests(unittest.TestCase):
    def test_procedural_gui_open_named_controls_undo_review_max_safe_save_restore(self):
        import tkinter as tk
        from koei_editor.games.uncharted_waters2_dos.editor import Editor
        root = tk.Tk()
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                source, target, restored = (directory / name for name in ('copy.dat', 'edited.dat', 'restored.dat'))
                source.write_bytes(procedural_raw())
                editor = Editor(root)
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)), \
                     patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                    editor.open()
                    errors.assert_not_called()
                self.assertEqual(len(editor.presentation.inspection_tables(editor.document)), 2)
                field = parser.fields_for(editor.document)[0]
                editor.fields.selection_set(field.id)
                editor.value.set('987')
                editor.apply_selected()
                self.assertEqual(editor.changes, {field.id: 987})
                editor.undo()
                self.assertEqual(editor.changes, {})
                editor.value.set('987')
                editor.apply_selected()
                editor.review()
                next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel)).destroy()
                editor.apply_theme('Dark')
                with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(target)), \
                     patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                    editor.save_as()
                    errors.assert_not_called()
                self.assertEqual(parser.field_map(parser.read_save(target))[field.id].value(editor.document.payload), 987)
                backup = next((directory / 'WarriorsEditorBackups').glob('*.dat'))
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(backup)), \
                     patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(restored)), \
                     patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                    editor.restore()
                    errors.assert_not_called()
                self.assertEqual(restored.read_bytes(), source.read_bytes())
        finally:
            root.destroy()
