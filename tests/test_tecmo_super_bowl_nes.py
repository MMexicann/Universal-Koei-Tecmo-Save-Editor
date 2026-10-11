"""Procedural non-playable SRAM tests; optional genuine public SRAM qualification."""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.tecmo_super_bowl_nes import parser
from koei_editor.games.tecmo_super_bowl_nes.editor import Editor


def generated_raw():
    raw = bytearray((i * 19 + 47) & 255 for i in range(8192))
    raw[0x6B7:0x6BE] = b'AKIHIKO'
    for i in range(28):
        base = 0x7AE + i * 208 + (260 if i >= 9 else 0)
        raw[base + 0xBD:base + 0xC1] = bytes((0x01, 0x23, 0x45, 0x67))
        raw[base + 0xC5:base + 0xC8] = b'\0\0\0'
    raw[0x6BE:0x6C0] = ((sum(raw[0x6C0:0xEFE]) + sum(raw[0x1002:0x1F72]) + 0x3412)
                           & 65535).to_bytes(2, 'little')
    return bytes(raw)


class TecmoSuperBowlTests(unittest.TestCase):
    def setUp(self):
        self.doc = parser.decode(generated_raw())

    def test_exact_noop_and_native_pointer_gap(self):
        self.assertEqual(parser.serialize(self.doc, {}), self.doc.raw)
        self.assertEqual(len(parser.fields_for(self.doc)), 1092)
        self.assertEqual(parser.team_base(8), 0xE2E)
        self.assertEqual(parser.team_base(9), 0x1002)
        self.assertEqual(parser.team_base(27), 0x1EA2)
        self.assertEqual(parser.field_map(self.doc)['team_9_condition_0'].offset, 0x10CA)
        self.assertEqual(parser.field_map(self.doc)['team_27_condition_29'].offset, 0x1F71)
        self.assertFalse(self.doc.format.game_load_verified)

    def test_checksum_both_regions_boundaries_and_excluded_gap(self):
        for offset in (0x6C0, 0xEFD, 0x1002, 0x1F71, 0x6BE, 0x6BF):
            raw = bytearray(self.doc.raw)
            raw[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(SaveError):
                parser.decode(raw)
        for offset in (0x6C0 - 1, 0xEFE, 0x1001, 0x1F72, 0, 8191):
            if offset == 0x6BF:
                continue
            raw = bytearray(self.doc.raw)
            raw[offset] ^= 1
            self.assertEqual(parser.serialize(parser.decode(raw), {}), bytes(raw))

    def test_foreign_size_signature_state_and_game_rejection(self):
        for raw in (self.doc.raw[:-1], self.doc.raw + b'x', b'\0' * 8192,
                    b'NST\x1a' + self.doc.raw, b'NES\x1a' + self.doc.raw):
            with self.assertRaises(SaveError):
                parser.decode(raw)
        raw = bytearray(self.doc.raw)
        raw[0x6B7] ^= 1
        with self.assertRaises(SaveError):
            parser.decode(raw)
        with self.assertRaises(SaveError):
            parser.decode(self.doc.raw, 'monster_rancher_ds')

    def test_surgical_packed_edits_preserve_other_players_and_dependencies(self):
        fields = parser.field_map(self.doc)
        changes = {}
        for key, value in (('team_0_condition_0', 3), ('team_0_condition_1', 0),
                           ('team_9_condition_29', 2), ('team_9_play_0', 7),
                           ('team_9_play_1', 4), ('team_27_control', 1)):
            changes = parser.stage(self.doc, changes, key, value)
        output = parser.serialize(self.doc, changes)
        decoded = parser.decode(output)
        allowed = {fields[key].offset for key in changes} | {0x6BE, 0x6BF}
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(self.doc.raw, output))))
        self.assertEqual(output[0x10BF], 0x74)  # Team 10 first two slot choices, high then low.
        self.assertEqual(output[fields['team_0_condition_0'].offset] & 15,
                         self.doc.raw[fields['team_0_condition_0'].offset] & 15)
        self.assertEqual(output[0x69B + 27] & 0xFC, self.doc.raw[0x69B + 27] & 0xFC)
        for team in range(28):
            base = parser.team_base(team)
            self.assertEqual(output[base:base + 0xBD], self.doc.raw[base:base + 0xBD])
            self.assertEqual(output[base + 0xC1:base + 0xC8], self.doc.raw[base + 0xC1:base + 0xC8])
            self.assertEqual(output[base + 0xCF] & 15, self.doc.raw[base + 0xCF] & 15)
        for key, value in changes.items():
            self.assertEqual(parser.field_map(decoded)[key].value(decoded.raw), value)
        self.assertEqual(len(parser.review(self.doc, changes)), len(changes))

    def test_all_fields_surgical_and_unknown_nibbles_are_inspection_only(self):
        fields = parser.field_map(self.doc)
        changes = {key: (field.value(self.doc.raw) + 1) % (field.maximum + 1)
                   for key, field in fields.items()}
        output = parser.serialize(self.doc, changes)
        self.assertEqual(len(parser.fields_for(parser.decode(output))), 1092)
        allowed = {field.offset for field in fields.values()} | {0x6BE, 0x6BF}
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(self.doc.raw, output))))
        raw = bytearray(self.doc.raw)
        raw[0x7AE + 0xBD] = 0xF2
        raw[0x6BE:0x6C0] = parser.checksum(raw).to_bytes(2, 'little')
        doc = parser.decode(raw)
        self.assertNotIn('team_0_play_0', parser.field_map(doc))
        output = parser.serialize(doc, {'team_0_play_1': 6})
        self.assertEqual(output[0x7AE + 0xBD], 0xF6)
        self.assertEqual(parser.serialize(doc, {}), bytes(raw))
        with self.assertRaises(SaveError):
            parser.stage(doc, {}, 'team_0_play_0', 0)
        raw[0x7AE + 0xBD] = 0x2F
        raw[0x6BE:0x6C0] = parser.checksum(raw).to_bytes(2, 'little')
        doc = parser.decode(raw)
        self.assertNotIn('team_0_play_1', parser.field_map(doc))
        output = parser.serialize(doc, {'team_0_play_0': 6})
        self.assertEqual(output[0x7AE + 0xBD], 0x6F)

    def test_choices_bounds_malformed_keys_snapshot_and_unstage(self):
        self.assertEqual(parser.field_options(self.doc, 'team_0_condition_0')[3], (3, 'Excellent'))
        self.assertEqual(parser.field_options(self.doc, 'team_0_play_4')[0][1], 'Choice 1 (play ID 32)')
        self.assertEqual(parser.field_options(self.doc, 'team_0_control')[3][1], 'Skip (SKP)')
        for value in (-1, 4, True, 1.0, '1', None):
            with self.assertRaises(SaveError):
                parser.stage(self.doc, {}, 'team_0_condition_0', value)
        for key in ('unknown', [], {}):
            with self.subTest(key=key):
                for call in (lambda: parser.stage(self.doc, {}, key, 0),
                             lambda: parser.field_options(self.doc, key),
                             lambda: parser.limit_values(self.doc, {}, [key])):
                    with self.assertRaises(SaveError):
                        call()
        for changes in (None, [], {'unknown': 1}, {'team_0_play_0': 8}):
            with self.assertRaises(SaveError):
                parser.serialize(self.doc, changes)
        for forged in (replace(self.doc, payload=bytearray(self.doc.raw)),
                       replace(self.doc, raw=bytearray(self.doc.raw)),
                       replace(self.doc, format=replace(self.doc.format))):
            with self.assertRaises(SaveError):
                parser.serialize(forged, {})
        key = 'team_0_condition_0'
        changes = parser.stage(self.doc, {}, key, (parser.field_map(self.doc)[key].value(self.doc.raw) + 1) % 4)
        self.assertEqual(parser.stage(self.doc, changes, key, parser.field_map(self.doc)[key].value(self.doc.raw)), {})

    def test_max_only_conditions_and_preserves_pending_and_unknown_bytes(self):
        changes = {'team_0_control': 1, 'team_0_play_0': 4}
        output = parser.maximums(self.doc, changes)
        self.assertEqual(output['team_0_control'], 1)
        self.assertEqual(output['team_0_play_0'], 4)
        doc = parser.decode(parser.serialize(self.doc, output))
        self.assertEqual(doc.raw[0x7AE + 0xC8:0x7AE + 0xCF], b'\xff' * 7)
        self.assertEqual(doc.raw[0x7AE + 0xCF] & 15, self.doc.raw[0x7AE + 0xCF] & 15)
        self.assertEqual(parser.limit_values(self.doc, changes, ['team_0_control', 'team_0_play_0']), {})

    def test_injured_skill_conditions_are_read_only_and_max_preserves_them(self):
        raw = bytearray(self.doc.raw)
        raw[0x7AE + 0xC5] = 0x40  # QB1 Probable, QB2/RB1/RB2 healthy.
        raw[0x7AE + 0xC7] = 0x03  # TE2 Doubtful; condition shares a byte with WR3/WR4/TE1.
        raw[0x6BE:0x6C0] = parser.checksum(raw).to_bytes(2, 'little')
        doc = parser.decode(raw)
        self.assertNotIn('team_0_condition_0', parser.field_map(doc))
        self.assertNotIn('team_0_condition_11', parser.field_map(doc))
        self.assertIn('team_0_condition_1', parser.field_map(doc))
        for key in ('team_0_condition_0', 'team_0_condition_11'):
            with self.assertRaises(SaveError):
                parser.stage(doc, {}, key, 3)
        output = parser.serialize(doc, parser.maximums(doc, {}))
        self.assertEqual(output[0x7AE + 0xC8] & 0xC0, raw[0x7AE + 0xC8] & 0xC0)
        self.assertEqual(output[0x7AE + 0xCA] & 3, raw[0x7AE + 0xCA] & 3)
        self.assertEqual(output[0x7AE + 0xC5:0x7AE + 0xC8], raw[0x7AE + 0xC5:0x7AE + 0xC8])
        self.assertEqual(parser.player_records(doc)[0][3:], ('Probable', 'Read only: injured'))
        self.assertEqual(parser.player_records(doc)[11][3:], ('Doubtful', 'Read only: injured'))

    def test_copy_backup_restore_changed_source_and_destination_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'copy.sav'
            source.write_bytes(self.doc.raw)
            doc = parser.read_save(source)
            output = parser.save_as(doc, {'team_0_condition_0': 3}, root / 'edited.sav')
            self.assertEqual(source.read_bytes(), doc.raw)
            snapshot = parser.backup(doc)
            restored = parser.restore(snapshot, root / 'restored.sav')
            # Windows temporary paths may use an 8.3 alias; restore returns the
            # resolved destination, so compare canonical paths on every host.
            self.assertEqual(restored, (root / 'restored.sav').resolve())
            self.assertEqual(restored.read_bytes(), doc.raw)
            for destination in (source, root / 'edited.sav'):
                with self.assertRaises(FileExistsError):
                    parser.save_as(doc, {}, destination)
            with self.assertRaises(SaveError):
                parser.save_as(doc, {}, root / 'bad.nst')
            source.write_bytes(b'x')
            with self.assertRaises(SaveError):
                parser.backup(doc)
            with self.assertRaises(SaveError):
                parser.save_as(doc, {}, root / 'late.sav')
            self.assertFalse((root / 'late.sav').exists())
            self.assertEqual(parser.decode(output.raw).raw, output.raw)

    def test_public_native_sram_roundtrip_and_surgical_edits(self):
        paths = [Path(path) for path in os.environ.get('TSB_NES_NATIVE_COPIES', '').split(os.pathsep) if path]
        if not paths:
            self.skipTest('Private genuine public battery SRAM copies were not configured.')
        for path in paths:
            doc = parser.read_save(path)
            self.assertEqual(parser.serialize(doc, {}), path.read_bytes())
            changes = {'team_0_condition_0': 3, 'team_9_play_0': 7, 'team_27_control': 0}
            output = parser.serialize(doc, changes)
            allowed = {parser.field_map(doc)[key].offset for key in changes} | {0x6BE, 0x6BF}
            self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(doc.raw, output))))
            self.assertEqual(parser.decode(output).raw, output)
            for field in parser.fields_for(doc):
                value = (field.value(doc.raw) + 1) % (field.maximum + 1)
                edited = parser.serialize(doc, {field.id: value})
                mask = ((1 << field.bits) - 1) << field.shift
                self.assertEqual(edited[field.offset] & ~mask, doc.raw[field.offset] & ~mask)
                self.assertEqual(field.value(edited), value)
                self.assertTrue(all(a == b or i in (field.offset, 0x6BE, 0x6BF)
                                    for i, (a, b) in enumerate(zip(doc.raw, edited))))

    def test_final_source_change_after_backup_prevents_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'copy.sav'
            source.write_bytes(self.doc.raw)
            doc = parser.read_save(source)
            original = parser.snapshot_backup

            def race(*args, **kwargs):
                path = original(*args, **kwargs)
                source.write_bytes(b'changed during backup')
                return path

            with patch.object(parser, 'snapshot_backup', side_effect=race), self.assertRaises(SaveError):
                parser.save_as(doc, {}, root / 'late.sav')
            self.assertFalse((root / 'late.sav').exists())


class TecmoSuperBowlGuiTests(unittest.TestCase):
    def test_editor_load_search_choice_review_undo_and_safe_save(self):
        try:
            root = tk.Tk()
            root.geometry('1080x820')
        except tk.TclError as error:
            self.skipTest(str(error))
        try:
            with tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / 'copy.sav'
                native = [Path(path) for path in os.environ.get('TSB_NES_NATIVE_COPIES', '').split(os.pathsep) if path]
                opened_raw = native[0].read_bytes() if native else generated_raw()
                source.write_bytes(opened_raw)
                for theme in ('Light', 'Dark'):
                    host = ttk.Frame(root)
                    host.pack(fill='both', expand=True)
                    editor = Editor(root, parent=host, theme=theme)
                    with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)), \
                         patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                        editor.open()
                        errors.assert_not_called()
                    root.update()
                    self.assertEqual(len(editor.backend.fields_for(editor.document)), len(parser.fields_for(parser.decode(opened_raw))))
                    self.assertEqual(len(editor.presentation.inspection_tables(editor.document)[0].rows), 28)
                    editor.search.set('team_9_play_0')
                    root.update()
                    self.assertEqual(editor.fields.get_children(), ('team_9_play_0',))
                    editor.fields.selection_set('team_9_play_0')
                    editor.selected()
                    self.assertEqual(len(editor.value_choice.cget('values')), 8)
                    editor.value.set('7')
                    editor.apply_selected()
                    self.assertEqual(editor.changes, {'team_9_play_0': 7})
                    editor.undo()
                    self.assertEqual(editor.changes, {})
                    editor.value.set('7')
                    editor.apply_selected()
                    self.assertEqual(len(parser.review(editor.document, editor.changes)), 1)
                    editor.review()
                    dialog = next(child for child in root.winfo_children() if isinstance(child, tk.Toplevel))
                    dialog.destroy()
                    destination = Path(directory) / f'{theme}.sav'
                    with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(destination)), \
                         patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                        editor.save_as()
                        errors.assert_not_called()
                    self.assertEqual(parser.read_save(destination).payload[0x10BF] >> 4, 7)
                    self.assertEqual(source.read_bytes(), opened_raw)
                    host.destroy()
        finally:
            root.destroy()
