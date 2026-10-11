"""Non-playable generated DOS profiles and optional upstream reference snapshots."""
from dataclasses import replace
from functools import lru_cache
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.rotk2_dos import parser


@lru_cache(maxsize=1)
def generated_raw():
    raw = bytearray((index * 17 + 23) & 255 for index in range(parser.SIZE))
    raw[:10] = b'1990.02.19'
    struct.pack_into('<H', raw, 12, 200)
    raw[14:16] = bytes((2, 1))
    for index in range(parser.OFFICER_COUNT):
        struct.pack_into('<H', raw, parser.OFFICER_START + parser.OFFICER_STRIDE * index, 0)
    for index in range(parser.PROVINCE_COUNT):
        base = parser.PROVINCE_START + parser.PROVINCE_STRIDE * index
        struct.pack_into('<HHHHHIH', raw, base, 0, 0, 0, 0, 1000 + index, 50000 + index, 1200)
        raw[base + 16:base + 18] = bytes((0 if index < 2 else 255, 255))
        raw[base + 32:base + 35] = bytes((index % 8, index // 8, index % 14))
    return bytes(raw)


class Rotk2DosTests(unittest.TestCase):
    def setUp(self):
        self.doc = parser.decode(generated_raw())

    def test_noop_and_all_resource_edits_preserve_every_unknown_and_tail_byte(self):
        self.assertFalse(self.doc.format.sample_verified)
        self.assertFalse(self.doc.format.editing_verified)
        self.assertFalse(self.doc.format.game_load_verified)
        self.assertTrue(self.doc.format.published_format)
        self.assertEqual(parser.serialize(self.doc, {}), self.doc.raw)
        fields = parser.fields_for(self.doc)
        self.assertEqual(len(fields), 4)
        changes = {field.id: 0 for field in fields}
        edited = parser.decode(parser.serialize(self.doc, changes))
        allowed = {field.offset + offset for field in fields for offset in range(field.size)}
        self.assertTrue(all(a == b or offset in allowed for offset, (a, b) in enumerate(zip(self.doc.raw, edited.raw))))
        self.assertEqual(edited.raw[0x337F:], self.doc.raw[0x337F:])
        self.assertEqual(len(parser.review(self.doc, changes)), 4)
        self.assertEqual(parser.maximums(self.doc, changes), changes)
        self.assertEqual(parser.limit_values(self.doc, {}, tuple(changes)), {})
        self.assertTrue(all(not field.maxable for field in fields))
        for field in fields:
            self.assertEqual(parser.stage(self.doc, {field.id: 0}, field.id, field.value(self.doc.payload)), {})

    def test_size_signature_calendar_and_province_geometry_reject_foreign_or_malformed_input(self):
        for raw in (generated_raw()[:-1], generated_raw() + b'x', b'\0' * parser.SIZE):
            with self.assertRaises(SaveError):
                parser.decode(raw)
        for offset, value in ((0, b'x'), (14, b'\x0c'), (15, b'\0'),
                              (parser.PROVINCE_START + 16, b'\x10'),
                              (parser.PROVINCE_START + 32, b'\x08'),
                              (parser.PROVINCE_START + 34, b'\x0e')):
            raw = bytearray(generated_raw())
            raw[offset:offset + len(value)] = value
            with self.assertRaises(SaveError):
                parser.decode(raw)
        raw = bytearray(generated_raw())
        base = parser.PROVINCE_START
        raw[base + 35 + 32:base + 35 + 34] = raw[base + 32:base + 34]
        with self.assertRaises(SaveError):
            parser.decode(raw)
        with self.assertRaises(SaveError):
            parser.decode(generated_raw(), 'rotk2_snes')

    def test_invalid_record_pointers_cycles_and_cross_owner_chains_reject(self):
        for offset, value in ((parser.PROVINCE_START, parser.PROVINCE_START + 57),
                              (parser.PROVINCE_START + 2, parser.PROVINCE_START + 56),
                              (parser.OFFICER_START, parser.OFFICER_START + 56),
                              (parser.PROVINCE_START, parser.PROVINCE_START + 56)):
            raw = bytearray(generated_raw())
            struct.pack_into('<H', raw, offset, value)
            with self.assertRaises(SaveError):
                parser.decode(raw)
        raw = bytearray(generated_raw())
        struct.pack_into('<H', raw, parser.PROVINCE_START, parser.PROVINCE_START + 2 * 35 + 56)
        with self.assertRaises(SaveError):
            parser.decode(raw)

    def test_bounds_ownership_snapshot_and_unknown_field_protection(self):
        field = parser.fields_for(self.doc)[0]
        self.assertNotIn('province_2_gold', parser.field_map(self.doc))
        for changes in ({field.id: -1}, {field.id: field.maximum + 1}, {field.id: True},
                        {'province_2_gold': 1}, {'year': 189}, None, []):
            with self.assertRaises(SaveError):
                parser.serialize(self.doc, changes)
        for forged in (replace(self.doc, payload=bytearray(self.doc.payload)),
                       replace(self.doc, raw=bytearray(self.doc.raw)),
                       replace(self.doc, format=replace(self.doc.format))):
            with self.assertRaises(SaveError):
                parser.serialize(forged, {})
        raw = bytearray(generated_raw())
        struct.pack_into('<H', raw, field.offset, 65535)
        doc = parser.decode(raw)
        self.assertEqual(parser.serialize(doc, {}), bytes(raw))
        self.assertEqual(parser.maximums(doc, {}), {})
        changes = parser.stage(doc, {}, field.id, 0)
        self.assertEqual(parser.stage(doc, changes, field.id, 65535), {})

    def test_safe_save_backup_restore_and_existing_or_changed_source_rejection(self):
        for extension in ('', '.sav', '.dat'):
            with self.subTest(extension=extension), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / ('copy' + extension)
                target, restored = root / ('edited' + extension), root / ('restored' + extension)
                source.write_bytes(self.doc.raw)
                doc = parser.read_save(source)
                key = parser.fields_for(doc)[0].id
                edited = parser.save_as(doc, {key: 0}, target)
                self.assertEqual(parser.field_map(edited)[key].value(edited.payload), 0)
                self.assertEqual(source.read_bytes(), doc.raw)
                backup = parser.backup(doc)
                parser.restore(backup, restored)
                self.assertEqual(restored.read_bytes(), doc.raw)
                for destination in (source, target):
                    with self.assertRaises(FileExistsError):
                        parser.save_as(doc, {}, destination)
                source.write_bytes(b'externally changed')
                with self.assertRaises(SaveError):
                    parser.backup(doc)
                with self.assertRaises(SaveError):
                    parser.save_as(doc, {}, root / ('changed' + extension))

    def test_final_source_check_and_live_game_directory_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root / 'copy.sav', root / 'edited.sav'
            source.write_bytes(self.doc.raw)
            doc = parser.read_save(source)
            original_snapshot = parser.snapshot_backup

            def mutated_snapshot(*args, **kwargs):
                backup = original_snapshot(*args, **kwargs)
                source.write_bytes(b'changed while backing up')
                return backup

            with patch.object(parser, 'snapshot_backup', side_effect=mutated_snapshot):
                with self.assertRaises(SaveError):
                    parser.save_as(doc, {}, destination)
            self.assertFalse(destination.exists())
            source.write_bytes(self.doc.raw)
            (root / 'MAIN.EXE').write_bytes(b'not an executable; path-guard test only')
            (root / 'SCENARIO.DAT').write_bytes(b'not a game asset; path-guard test only')
            with self.assertRaises(SaveError):
                parser.read_save(source)
            with self.assertRaises(SaveError):
                parser.save_as(doc, {}, destination)

    @unittest.skipUnless(os.environ.get('ROTK2_DOS_REFERENCE_DIR'), 'Published reference snapshots not selected')
    def test_source_reference_snapshots_are_not_counted_as_genuine_player_save_proof(self):
        files = sorted(Path(os.environ['ROTK2_DOS_REFERENCE_DIR']).glob('S[0-6]'))
        self.assertEqual(len(files), 7)
        for source in files:
            doc = parser.read_save(source)
            self.assertFalse(doc.format.sample_verified)
            self.assertEqual(parser.serialize(doc, {}), doc.raw)
            fields = parser.fields_for(doc)
            changes = {field.id: 0 for field in fields}
            edited = parser.decode(parser.serialize(doc, changes))
            allowed = {field.offset + offset for field in fields for offset in range(field.size)}
            self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(doc.raw, edited.raw))))
            self.assertEqual(parser.province_records(doc)[0][4], int.from_bytes(doc.raw[0x2D8C + 14:0x2D8C + 16], 'little') * 100)


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'Graphical display required')
class Rotk2DosGuiTests(unittest.TestCase):
    def test_source_reference_or_generated_editor_undo_review_safe_save_and_restore(self):
        import tkinter as tk
        from koei_editor.games.rotk2_dos.editor import Editor
        root = tk.Tk()
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                reference = os.environ.get('ROTK2_DOS_REFERENCE_DIR')
                raw = (Path(reference) / 'S1').read_bytes() if reference else generated_raw()
                source, target, restored = directory / 'copy', directory / 'edited', directory / 'restored'
                source.write_bytes(raw)
                editor = Editor(root)
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)), \
                     patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                    editor.open()
                    errors.assert_not_called()
                self.assertEqual(len(editor.presentation.inspection_tables(editor.document)[0].rows), 41)
                field = parser.fields_for(editor.document)[0]
                editor.fields.selection_set(field.id)
                editor.value.set('0')
                editor.apply_selected()
                self.assertEqual(editor.changes, {field.id: 0})
                editor.undo()
                self.assertEqual(editor.changes, {})
                editor.value.set('0')
                editor.apply_selected()
                editor.review()
                next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel)).destroy()
                editor.apply_theme('Dark')
                with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(target)), \
                     patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                    editor.save_as()
                    errors.assert_not_called()
                self.assertEqual(parser.field_map(parser.read_save(target))[field.id].value(editor.document.payload), 0)
                backup = next(path for path in (directory / 'WarriorsEditorBackups').iterdir()
                              if path.suffix == '')
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(backup)), \
                     patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(restored)), \
                     patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                    editor.restore()
                    errors.assert_not_called()
                self.assertEqual(restored.read_bytes(), raw)
                self.assertEqual(source.read_bytes(), raw)
        finally:
            root.destroy()
