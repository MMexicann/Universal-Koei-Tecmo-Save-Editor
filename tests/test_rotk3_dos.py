"""Procedural occupied tables plus optional initialized original native input.

Generated tables are not playable saves and do not establish genuine campaign
editing or game-load validation.
"""
from dataclasses import replace
from functools import lru_cache
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.rotk3_dos import parser


@lru_cache(maxsize=1)
def generated_raw():
    raw = bytearray((index * 19 + 7) & 255 for index in range(parser.SIZE))
    raw[:10] = parser.SIGNATURE
    for slot in range(10):
        directory = 10 + 14 * slot
        raw[directory:directory + 14] = bytes.fromhex('00000000FF00FF8C4E8EE596BC00')
    for slot in (0, 9):
        directory = 10 + 14 * slot
        struct.pack_into('<H', raw, directory, 194)
        raw[directory + 2:directory + 7] = bytes((1, 1, 4, 2, 1))
        start = slot * 0xCE01
        for city in range(45):
            base = start + 0x1B8 + city * 74
            struct.pack_into('<hhhh', raw, base + 8, city if city < 2 else -1, -1, -1, -1)
            raw[base + 65:base + 69] = bytes((0x80, city + 1, 0x81, city + 1))
            struct.pack_into('<HI', raw, base + 26, 1234 + city, 50000 + city)
            struct.pack_into('<HHHH', raw, base + 46, 500, 200, 100, 90)
            raw[base + 57:base + 60] = bytes((6, 4, 2))
        for officer in range(600):
            base = start + 0x544E + officer * 49
            raw[base + 18:base + 20] = b'\0\0'
            if officer < 4:
                struct.pack_into('<hH', raw, base + 3, -1, 1234)
                raw[base + 16:base + 22] = bytes((30, 40, 50, 60, 70, 80))
                raw[base + 26] = 0
    return bytes(raw)


class Rotk3DosTests(unittest.TestCase):
    def setUp(self):
        self.doc = parser.decode(generated_raw())

    def test_exact_noop_and_each_field_surgical_native_record_writer(self):
        self.assertEqual(parser.serialize(self.doc, {}), generated_raw())
        self.assertFalse(self.doc.format.editing_verified)
        self.assertFalse(self.doc.format.sample_verified)
        self.assertFalse(self.doc.format.game_load_verified)
        self.assertEqual(len(parser.fields_for(self.doc)), 84)
        self.assertEqual(len(parser.city_records(self.doc)), 90)
        self.assertEqual(len(parser.officer_records(self.doc)), 8)
        for field in parser.fields_for(self.doc):
            value = 100 if '_o' in field.id else 0
            changes = parser.stage(self.doc, {}, field.id, value)
            actual = parser.serialize(self.doc, changes)
            expected = bytearray(self.doc.raw)
            # Independent offset/width primitive reproduces the external whole
            # record writer's direct native assignment without importing it.
            struct.pack_into({1: '<B', 2: '<H', 4: '<I'}[field.size], expected, field.offset, value)
            self.assertEqual(actual, bytes(expected), field.id)
            self.assertEqual(parser.decode(actual).payload, actual)
            self.assertEqual(parser.stage(self.doc, changes, field.id, field.value(self.doc.raw)), {})
        changes = {field.id: (100 if '_o' in field.id else 0) for field in parser.fields_for(self.doc)}
        edited = parser.serialize(self.doc, changes)
        allowed = {field.offset + n for field in parser.fields_for(self.doc) for n in range(field.size)}
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(self.doc.raw, edited))))
        self.assertEqual(edited[527520:], self.doc.raw[527520:])
        self.assertEqual(edited[10:150], self.doc.raw[10:150])
        self.assertEqual(len(parser.review(self.doc, changes)), 84)

    def test_initialized_slots_are_read_only_and_never_interpreted_as_campaigns(self):
        raw = bytearray(generated_raw())
        for slot in (0, 9):
            directory = 10 + 14 * slot
            raw[directory:directory + 14] = bytes.fromhex('00000000FF00FF8C4E8EE596BC00')
        doc = parser.decode(raw)
        self.assertEqual(parser.fields_for(doc), ())
        self.assertEqual(parser.city_records(doc), ())
        self.assertEqual(parser.officer_records(doc), ())
        self.assertEqual(parser.serialize(doc, {}), bytes(raw))
        with self.assertRaises(SaveError):
            parser.stage(doc, {}, 's0_o0_war', 100)

    def test_header_build_directory_names_and_record_geometry_rejection(self):
        for raw in (generated_raw()[:-1], generated_raw() + b'x', bytes(parser.SIZE),
                    b'1992.01.08' + bytes(648700), b'1992.01.08' + bytes(605510)):
            with self.assertRaises(SaveError):
                parser.decode(raw)
        for offset, value in ((0, b'X'), (12, b'\0'), (14, b'\x2d'), (15, b'\x07'),
                              (16, b'\x02'), (24, b'\x01'), (0x1B8 + 65, b'\0' * 4),
                              (0x1B8 + 8, struct.pack('<h', 600))):
            raw = bytearray(generated_raw())
            raw[offset:offset + len(value)] = value
            with self.assertRaises(SaveError):
                parser.decode(raw)
        raw = bytearray(generated_raw())
        raw[0x1B8 + 74 + 65:0x1B8 + 74 + 69] = raw[0x1B8 + 65:0x1B8 + 69]
        with self.assertRaises(SaveError):
            parser.decode(raw)
        raw = bytearray(generated_raw())
        struct.pack_into('<h', raw, 0x544E + 3, 1)
        struct.pack_into('<h', raw, 0x544E + 49 + 3, 0)
        with self.assertRaises(SaveError):
            parser.decode(raw)
        with self.assertRaises(SaveError):
            parser.decode(generated_raw(), 'rotk3_snes')

    def test_ownership_unusual_abilities_empty_slots_and_resource_limits(self):
        fields = parser.field_map(self.doc)
        self.assertNotIn('s1_o0_war', fields)
        self.assertNotIn('s0_c2_gold', fields)
        self.assertTrue(all(not field.maxable for field in fields.values()))
        self.assertEqual(parser.maximums(self.doc, {'s0_o0_war': 100}), {'s0_o0_war': 100})
        self.assertEqual(parser.limit_values(self.doc, {}, tuple(fields)), {})
        for changes in ({'s0_o0_war': 0}, {'s0_o0_war': 101}, {'s0_o0_war': True},
                        {'s0_c0_gold': 1235}, {'s1_o0_war': 100}, {'s0_c0_owner': 1}, [], None):
            with self.assertRaises(SaveError):
                parser.serialize(self.doc, changes)
        raw = bytearray(generated_raw())
        raw[0x544E + 16] = 127
        raw[0x544E + 49 + 26] = 255
        doc = parser.decode(raw)
        self.assertNotIn('s0_o0_land', parser.field_map(doc))
        self.assertNotIn('s0_c1_gold', parser.field_map(doc))
        self.assertEqual(parser.officer_records(doc)[0][3], 127)
        self.assertEqual(parser.serialize(doc, {}), bytes(raw))
        self.assertEqual(parser.maximums(doc, {}), {})
        for key in ([], {}, None):
            with self.assertRaises(SaveError):
                parser.stage(self.doc, {}, key, 0)
            with self.assertRaises(SaveError):
                parser.field_hint(self.doc, key)
            with self.assertRaises(SaveError):
                parser.limit_values(self.doc, {}, (key,))

    def test_immutable_snapshot_contract(self):
        for doc in (replace(self.doc, raw=bytearray(self.doc.raw)),
                    replace(self.doc, source=[]),
                    replace(self.doc, source=None),
                    replace(self.doc, payload=bytearray(self.doc.raw)),
                    replace(self.doc, payload=self.doc.raw[:-1]),
                    replace(self.doc, format=replace(self.doc.format))):
            with self.assertRaises(SaveError):
                parser.serialize(doc, {})

    def test_save_backup_restore_hash_game_source_and_alias_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target, restored = root / 'copy.sav', root / 'edited.sav', root / 'restored.sav'
            source.write_bytes(self.doc.raw)
            doc = parser.read_save(source)
            edited = parser.save_as(doc, {'s0_o0_war': 100}, target)
            self.assertEqual(parser.field_map(edited)['s0_o0_war'].value(edited.raw), 100)
            self.assertEqual(source.read_bytes(), self.doc.raw)
            backup = parser.backup(doc)
            parser.restore(backup, restored)
            self.assertEqual(restored.read_bytes(), self.doc.raw)
            for destination in (source, target):
                with self.assertRaises(FileExistsError):
                    parser.save_as(doc, {}, destination)
            alias = root / 'alias.sav'
            os.link(source, alias)
            with self.assertRaises(FileExistsError):
                parser.save_as(doc, {}, alias)
            damaged = bytearray(backup.read_bytes())
            damaged[-1] ^= 1
            backup.write_bytes(damaged)
            with self.assertRaises(SaveError):
                parser.restore(backup, root / 'bad.sav')
            self.assertFalse((root / 'bad.sav').exists())
            source.write_bytes(b'changed')
            with self.assertRaises(SaveError):
                parser.backup(doc)
            with self.assertRaises(SaveError):
                parser.save_as(doc, {}, root / 'changed.sav')

    def test_source_race_live_folder_extension_and_wrong_game_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'copy.sav'
            source.write_bytes(self.doc.raw)
            doc = parser.read_save(source)
            original = parser.snapshot_backup

            def change_after_backup(*args, **kwargs):
                result = original(*args, **kwargs)
                source.write_bytes(b'changed')
                return result

            target = root / 'raced.sav'
            with patch.object(parser, 'snapshot_backup', side_effect=change_after_backup):
                with self.assertRaises(SaveError):
                    parser.save_as(doc, {}, target)
            self.assertFalse(target.exists())
            source.write_bytes(self.doc.raw)
            backup = parser.backup(doc)
            manifest = backup.with_suffix('.json')
            import json
            data = json.loads(manifest.read_text())
            data['game_id'] = 'rotk2_dos'
            manifest.write_text(json.dumps(data))
            with self.assertRaises(SaveError):
                parser.restore(backup, root / 'foreign.sav')
            with self.assertRaises(SaveError):
                parser.save_as(doc, {}, root / 'edited.dat')
            (root / 'MAIN.EXE').write_bytes(b'not executed')
            (root / 'KOEI.COM').write_bytes(b'not executed')
            with self.assertRaises(SaveError):
                parser.read_save(source)

    def test_optional_actual_initialized_native_noop_and_readonly_directory(self):
        location = os.environ.get('ROTK3_DOS_INITIAL_COPY')
        if not location:
            self.skipTest('Private original initialized TC native file was not supplied.')
        doc = parser.read_save(Path(location))
        self.assertEqual(doc.raw[:10], b'1992.01.08')
        self.assertEqual(len(doc.raw), 662640)
        self.assertEqual(parser.fields_for(doc), ())
        self.assertTrue(all(row[1] == 'Empty' for row in parser.slot_records(doc)))
        self.assertEqual(parser.serialize(doc, {}), Path(location).read_bytes())
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'copy.sav'
            source.write_bytes(doc.raw)
            copied = parser.read_save(source)
            saved = parser.save_as(copied, {}, Path(directory) / 'saved.sav')
            self.assertEqual(saved.raw, doc.raw)


class Rotk3DosGuiTests(unittest.TestCase):
    def test_generated_editor_apply_undo_review_inspector_theme_safe_save(self):
        import tkinter as tk
        from koei_editor.games.rotk3_dos.editor import Editor
        root = tk.Tk()
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as directory:
                rootdir = Path(directory)
                source, target = rootdir / 'copy.sav', rootdir / 'edited.sav'
                source.write_bytes(generated_raw())
                editor = Editor(root)
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)), \
                     patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                    editor.open()
                    errors.assert_not_called()
                self.assertEqual(len(editor.presentation.inspection_tables(editor.document)), 3)
                key = 's0_o0_war'
                editor.fields.selection_set(key)
                editor.value.set('100')
                editor.apply_selected()
                self.assertEqual(editor.changes, {key: 100})
                editor.undo()
                self.assertEqual(editor.changes, {})
                editor.value.set('100')
                editor.apply_selected()
                editor.review()
                next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel)).destroy()
                editor.apply_theme('Dark')
                with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(target)), \
                     patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                    editor.save_as()
                    errors.assert_not_called()
                doc = parser.read_save(target)
                self.assertEqual(parser.field_map(doc)[key].value(doc.raw), 100)
                self.assertEqual(source.read_bytes(), generated_raw())
        finally:
            root.destroy()

    def test_optional_initialized_native_gui_open_has_no_writable_fields(self):
        location = os.environ.get('ROTK3_DOS_INITIAL_COPY')
        if not location:
            self.skipTest('Private original initialized TC native file was not supplied.')
        import tkinter as tk
        from koei_editor.games.rotk3_dos.editor import Editor
        root = tk.Tk()
        root.withdraw()
        try:
            editor = Editor(root)
            with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=location), \
                 patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                editor.open()
                errors.assert_not_called()
            self.assertEqual(editor.fields.get_children(), ())
            self.assertEqual(len(editor.presentation.inspection_tables(editor.document)[0].rows), 10)
            editor.apply_theme('Dark')
        finally:
            root.destroy()
