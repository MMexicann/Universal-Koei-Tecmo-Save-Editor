"""Generated non-playable Ryza 2 Switch profile and private modified-reference checks."""
from functools import lru_cache
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.ryza import codec, parser
from tests.test_ryza_format import procedural_payload, node

GAME = 'atelier_ryza2_switch'


@lru_cache(maxsize=1)
def generated_payload():
    payload = procedural_payload().replace(bytes.fromhex('0000000100000001'), bytes.fromhex('0000000100000000'), 1)
    tree = parser._unique(parser._nodes(payload, 32, len(payload)), b'AlchemyTree')
    body = (node('ver', bytes.fromhex('000000020004'))
            + node('SkillPoint', struct.pack('>II', 4, 500))
            + node('SkillState', bytes(range(32))))
    return payload[:tree.start] + node('AlchemyTree', body) + payload[tree.end:]


def raw_for(payload=None, revision=0):
    if payload is None and revision == 0:
        return _generated_raw()
    header = bytearray((i * 29 + 5) & 255 for i in range(256))
    header[:48] = b'\1' + bytes(39) + struct.pack('<II', 1, revision)
    return codec.encode_file(bytes(header), generated_payload() if payload is None else payload,
                             0x12345678, b'\x13\x57\x9b')


@lru_cache(maxsize=1)
def _generated_raw():
    return raw_for(generated_payload())


class Ryza2SwitchTests(unittest.TestCase):
    def setUp(self):
        self.doc = parser.decode(raw_for(), GAME)

    def test_strict_title_revision_and_corruption_rejection(self):
        self.assertEqual(parser.serialize(self.doc, {}), self.doc.raw)
        for game in ('atelier_ryza2', 'atelier_ryza_switch', 'atelier_ryza'):
            with self.assertRaises(SaveError):
                parser.decode(self.doc.raw, game)
        for revision in (1, 2, 4):
            with self.assertRaises(SaveError):
                parser.decode(raw_for(revision=revision), GAME)
        for offset in (0, 40, 44, 256, len(self.doc.raw) - 10):
            raw = bytearray(self.doc.raw)
            raw[offset] ^= 1
            with self.assertRaises(SaveError):
                parser.decode(raw, GAME)
        for payload in (self.doc.payload[:-1], self.doc.payload + node('item', b'x'),
                        self.doc.payload.replace(b'_T_CENTRAL', b'_T_INVALID')):
            with self.assertRaises(SaveError):
                parser.decode(raw_for(payload), GAME)

    def test_sp_is_big_endian_reduction_preserving_learned_state_and_every_other_byte(self):
        field = parser.field_map(self.doc)['skill_points']
        self.assertEqual((field.size, field.byteorder, field.maximum, field.minimum), (4, 'big', 500, 0))
        self.assertFalse(field.maxable)
        for value in (0, 1, 499):
            changes = parser.stage(self.doc, {}, field.id, value)
            edited = parser.decode(parser.serialize(self.doc, changes), GAME)
            self.assertEqual(field.value(edited.payload), value)
            self.assertEqual(edited.payload[field.offset:field.offset + 4], value.to_bytes(4, 'big'))
            allowed = set(range(field.offset, field.offset + 4))
            self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(self.doc.payload, edited.payload))))
            self.assertEqual((edited.header, edited.seed, edited.footer, edited.trailer),
                             (self.doc.header, self.doc.seed, self.doc.footer, self.doc.trailer))
            self.assertEqual(parser.stage(self.doc, changes, field.id, 500), {})
        self.assertEqual(parser.maximums(self.doc, {}), {})
        for value in (-1, 501, True, '1'):
            with self.assertRaises(SaveError):
                parser.stage(self.doc, {}, field.id, value)

    def test_unknown_sp_framing_omits_control_instead_of_guessing(self):
        field = parser.field_map(self.doc)['skill_points']
        for offset, value in ((field.offset - 4, b'\0\0\0\2'),
                              (field.offset, b'\xff\xff\xff\xff')):
            payload = bytearray(self.doc.payload)
            payload[offset:offset + 4] = value
            doc = parser.decode(raw_for(bytes(payload)), GAME)
            self.assertNotIn('skill_points', parser.field_map(doc))
            self.assertEqual(parser.serialize(doc, {}), doc.raw)

    def test_quality_needs_zero_adjacent_value_and_never_changes_that_word(self):
        self.assertEqual(tuple(parser.field_map(self.doc)), ('skill_points',))
        records, quality_offset = parser._structure(self.doc.payload, GAME)
        record = next(r for r in records if r[0] == 'container')
        offset = record[3] + quality_offset
        payload = bytearray(self.doc.payload)
        struct.pack_into('<H', payload, offset + 2, 0)
        doc = parser.decode(raw_for(bytes(payload)), GAME)
        field = parser.field_map(doc)['container_0_quality']
        self.assertFalse(field.maxable)
        edited = parser.decode(parser.serialize(doc, {field.id: 99}), GAME)
        allowed = {offset, offset + 1}
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(doc.payload, edited.payload))))
        self.assertEqual(edited.payload[offset + 2:offset + 4], b'\0\0')
        self.assertNotIn('important_0_quality', parser.field_map(doc))
        with self.assertRaises(SaveError):
            parser.stage(doc, {}, field.id, 101)

    def test_safe_save_backup_restore_and_changed_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'copy.dat'
            source.write_bytes(self.doc.raw)
            doc = parser.read_save(source, GAME)
            field = parser.field_map(doc)['skill_points']
            edited = parser.save_as(doc, {field.id: 0}, root / 'edited.dat')
            self.assertEqual(field.value(edited.payload), 0)
            self.assertEqual(source.read_bytes(), doc.raw)
            backup = parser.backup(doc)
            parser.restore(backup, root / 'restored.dat', GAME)
            self.assertEqual((root / 'restored.dat').read_bytes(), doc.raw)
            source.write_bytes(b'changed externally')
            with self.assertRaises(SaveError):
                parser.backup(doc)
            with self.assertRaises(SaveError):
                parser.save_as(doc, {}, root / 'changed.dat')
            self.assertFalse((root / 'changed.dat').exists())

    @unittest.skipUnless(os.environ.get('RYZA2_SWITCH_SAVE_COPY'), 'Private original Ryza 2 Switch gameplay export not selected')
    def test_native_modified_reference_surgical_sp_and_copied_file_workflow(self):
        raw = Path(os.environ['RYZA2_SWITCH_SAVE_COPY']).read_bytes()
        doc = parser.decode(raw, GAME)
        self.assertEqual(parser.serialize(doc, {}), raw)
        self.assertEqual(tuple(parser.field_map(doc)), ('skill_points',))
        self.assertEqual(len(parser.item_records(doc)), 249)
        field = parser.field_map(doc)['skill_points']
        self.assertEqual(field.value(doc.payload), 117431850)
        edited = parser.decode(parser.serialize(doc, {field.id: 0}), GAME)
        allowed = set(range(field.offset, field.offset + 4))
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(doc.payload, edited.payload))))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'copy.dat'
            source.write_bytes(raw)
            copied = parser.read_save(source, GAME)
            parser.save_as(copied, {field.id: 0}, root / 'edited.dat')
            backup = parser.backup(copied)
            parser.restore(backup, root / 'restored.dat', GAME)
            self.assertEqual((root / 'restored.dat').read_bytes(), raw)


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'Graphical display required')
class Ryza2SwitchGuiTests(unittest.TestCase):
    def test_native_or_generated_open_inspect_edit_undo_review_save_restore(self):
        import tkinter as tk
        from koei_editor.games.ryza.editor2switch import Editor
        root = tk.Tk()
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                source, target, restored = (directory / name for name in ('copy.dat', 'edited.dat', 'restored.dat'))
                native = os.environ.get('RYZA2_SWITCH_SAVE_COPY')
                raw = Path(native).read_bytes() if native else raw_for()
                source.write_bytes(raw)
                editor = Editor(root)
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)), \
                     patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                    editor.open()
                    errors.assert_not_called()
                self.assertTrue(editor.presentation.inspection_tables(editor.document)[0].rows)
                editor.fields.selection_set('skill_points')
                editor.value.set('0')
                editor.apply_selected()
                self.assertEqual(editor.changes, {'skill_points': 0})
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
                self.assertEqual(parser.field_map(parser.read_save(target, GAME))['skill_points'].value(editor.document.payload), 0)
                backup = next((directory / 'WarriorsEditorBackups').glob('*.dat'))
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(backup)), \
                     patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(restored)), \
                     patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                    editor.restore()
                    errors.assert_not_called()
                self.assertEqual(restored.read_bytes(), raw)
                self.assertEqual(source.read_bytes(), raw)
        finally:
            root.destroy()
