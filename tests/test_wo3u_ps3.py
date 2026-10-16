"""Procedural contracts and optional genuine US PS3 export qualification."""
from dataclasses import replace
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.wo3u_ps3 import parser


def metadata(directory=parser.TITLE_IDS[0]):
    key = b'SAVEDATA_DIRECTORY\0'
    value = directory.encode() + b'\0'
    return (struct.pack('<5I', 0x46535000, 0x101, 36, 36 + len(key), 1)
            + struct.pack('<HH3I', 0, 0x204, len(value), len(value), 0) + key + value)


def fixture():
    """Generated data, never a genuine or playable save."""
    data = bytearray(b'\xA5' * parser.SAVE_SIZE)
    data[:4] = parser.REVISION
    for index in range(150):
        base = parser.OFFICER_BASE - 10 + index * parser.OFFICER_STRIDE
        data[base:base + 4] = parser.OFFICER_MARKER
    for index in range(parser.WEAPON_COUNT):
        base = parser.WEAPON_BASE - 4 + index * parser.WEAPON_STRIDE
        data[base:base + 4] = parser.WEAPON_MARKER
        data[base + 4:base + 28] = bytes.fromhex('ffffff00ffffffffffffffff000000000000000000000000')
    base = parser.WEAPON_BASE
    data[base:base + 24] = bytes.fromhex('0a00040005060708ffffffff030405060000000000000000')
    for field in parser.FORMAT.fields:
        data[field.offset:field.offset + field.size] = (min(12, field.maximum)).to_bytes(field.size, 'little')
    return bytes(data)


class WO3UltimatePS3Tests(unittest.TestCase):
    def test_noop_surgery_review_undo_bounds_and_unknown_preservation(self):
        raw = fixture()
        document = parser.decode(raw)
        self.assertEqual(parser.serialize(document, {}), raw)
        mapping = parser.field_map(document)
        self.assertEqual(len(mapping), 2)
        for key in ('growth_points', 'gems'):
            field = mapping[key]
            value = field.minimum + 1
            changes = parser.stage(document, {}, key, value)
            output = parser.serialize(document, changes)
            self.assertEqual(output[:field.offset], raw[:field.offset])
            self.assertEqual(output[field.offset + field.size:], raw[field.offset + field.size:])
            self.assertEqual(parser.field_map(parser.decode(output))[key].value(output), value)
            self.assertEqual(parser.review(document, changes), [(field, field.value(raw), value)])
            self.assertEqual(parser.stage(document, changes, key, field.value(raw)), {})
            for invalid in (True, -1, field.maximum + 1, '1'):
                with self.assertRaises(SaveError):
                    parser.stage(document, {}, key, invalid)
        self.assertEqual(parser.maximums(document, {}), {})
        with self.assertRaises(SaveError):
            parser.stage(document, {'unknown': 1}, 'gems', 1)
        with self.assertRaises(SaveError):
            parser.stage(document, {'growth_points': True}, 'gems', 1)
        with self.assertRaises(SaveError):
            parser.serialize(document, [])

    def test_exact_ps3_structure_rejection_and_immutable_snapshot(self):
        raw = fixture()
        for invalid in (raw[:-1], raw + b'\0', bytearray(raw)):
            with self.assertRaises(SaveError):
                parser.decode(invalid)
        for offset in (0, parser.OFFICER_BASE - 10,
                       parser.OFFICER_BASE - 10 + 149 * parser.OFFICER_STRIDE,
                       parser.WEAPON_BASE - 4 + 2319 * parser.WEAPON_STRIDE):
            invalid = bytearray(raw)
            invalid[offset] ^= 1
            with self.assertRaises(SaveError):
                parser.decode(bytes(invalid))
        # PC shares length/revision but has different runtime class markers.
        pc = bytearray(raw)
        pc[parser.OFFICER_BASE - 10:parser.OFFICER_BASE - 6] = bytes.fromhex('a86d0010')
        with self.assertRaises(SaveError):
            parser.decode(bytes(pc))
        document = parser.decode(raw)
        class ForgedFormat:
            def __eq__(self, other):
                return True
        for invalid in (replace(document, payload=raw[:-1]),
                        replace(document, format=replace(parser.FORMAT, id='wo3u')),
                        replace(document, format=ForgedFormat())):
            with self.assertRaises(SaveError):
                parser.fields_for(invalid)
        with self.assertRaises(SaveError):
            parser.decode(raw, 'wo3u')

    def test_rich_systems_inspected_only_and_unusual_resources_preserved(self):
        raw = bytearray(fixture())
        raw[0x137C:0x1380] = (7297309).to_bytes(4, 'little')
        document = parser.decode(bytes(raw))
        self.assertEqual(parser.maximums(document, {}), {})
        self.assertEqual(parser.serialize(document, {}), bytes(raw))
        self.assertEqual(parser.stage(document, {'gems': 5}, 'gems', 7297309), {})
        self.assertEqual({row['group'] for row in parser.inspection_rows(document)},
                         {'Progression', 'Weapons', 'Attribute orbs',
                          'Crafting materials', 'Other resources'})
        for key in ('weapon_0_rank_0', 'weapon_0_identity', 'weapon_0_slots',
                    'officer_0_health', 'officer_149_health', 'orb_0',
                    'material_6_144', 'crystals', 'tickets', 'officer_0_level',
                    'story_complete', 'relationship_1'):
            with self.assertRaises(SaveError):
                parser.stage(document, {}, key, 1)
        # No claimed blanket corruption detector: unknown gameplay bytes are
        # opaque. A changed unknown byte remains preserved by the no-op path.
        raw[-1] ^= 1
        self.assertEqual(parser.serialize(parser.decode(bytes(raw)), {}), bytes(raw))

    def test_required_exact_context_safe_save_backup_restore_and_changed_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'copy.bin'
            source.write_bytes(fixture())
            companion = root / 'PARAM.SFO'
            with self.assertRaises(SaveError):
                parser.read_save(source)
            for directory_id in ('NPUB30708-SAVEDATA', 'NPUB50173-SAVEDATA',
                                 'NPEB02052-SAVEDATA', 'NPUB31505-SAVEDATA-extra'):
                companion.write_bytes(metadata(directory_id))
                with self.assertRaises(SaveError):
                    parser.read_save(source)
            companion.write_bytes(metadata())
            document = parser.read_save(source)
            context_copy = root / 'self-test'
            context_copy.mkdir()
            parser.prepare_copy_context(document, context_copy)
            self.assertEqual((context_copy / 'PARAM.SFO').read_bytes(), companion.read_bytes())
            with self.assertRaises(FileExistsError):
                parser.prepare_copy_context(document, context_copy)
            snapshot = parser.backup(document)
            destination = root / 'edited.bin'
            saved = parser.save_as(document, {'gems': 321}, destination)
            self.assertEqual(parser.field_map(saved)['gems'].value(saved.payload), 321)
            self.assertEqual(source.read_bytes(), fixture())
            restored = parser.restore(snapshot, root / 'restored.bin')
            self.assertEqual(restored.read_bytes(), fixture())
            with self.assertRaises(FileExistsError):
                parser.save_as(document, {}, destination)
            companion.write_bytes(metadata() + b'\0')
            with self.assertRaises(SaveError):
                parser.save_as(document, {}, root / 'changed-context.bin')
            with self.assertRaises(SaveError):
                parser.prepare_copy_context(document, root / 'changed-context')
            companion.write_bytes(metadata())
            source.write_bytes(fixture()[:-1] + b'\x01')
            with self.assertRaises(SaveError):
                parser.save_as(document, {}, root / 'changed-source.bin')
            companion.unlink()
            with self.assertRaises(SaveError):
                parser.restore(snapshot, root / 'missing-context.bin')

    def test_optional_genuine_exports_noop_and_individual_field_families(self):
        value = os.environ.get('WO3U_PS3_US_COPIES')
        if not value:
            self.skipTest('No private genuine US PS3 Ultimate decrypted exports provided.')
        paths = [Path(p) for p in value.split(os.pathsep)]
        for path in paths:
            document = parser.read_save(path)
            self.assertEqual(parser.serialize(document, {}), document.raw)
            mapping = parser.field_map(document)
            keys = ['growth_points', 'gems']
            for key in keys:
                field = mapping[key]
                changed = parser.serialize(document, {key: field.minimum + 1})
                self.assertEqual(changed[:field.offset], document.raw[:field.offset])
                self.assertEqual(changed[field.offset + field.size:], document.raw[field.offset + field.size:])
                parser.decode(changed)

    def test_registered_copied_self_test_with_opaque_context(self):
        from koei_editor.shared.verified_self_test import run
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'copy.bin'
            source.write_bytes(fixture())
            source.with_name('PARAM.SFO').write_bytes(metadata())
            output = Path(directory) / 'self-test'
            report = run(parser.GAME_ID, source, output)
            self.assertTrue(report['success'])
            self.assertEqual(report['fields_checked'], 2)
            self.assertEqual(report['fields_changed'], 0)
            self.assertEqual(report['integrity_kind'], 'external')
            self.assertFalse(report['native_integrity_verified'])
            self.assertFalse(report['in_game_load_tested'])
            self.assertEqual((output / 'PARAM.SFO').read_bytes(), metadata())
            self.assertEqual((output / 'restored.bin').read_bytes(), fixture())
            self.assertEqual(source.read_bytes(), fixture())
            with self.assertRaises(SaveError):
                run(parser.GAME_ID, source, output)

    def test_tk_controls_review_undo_inspection_theme_save_restore(self):
        import tkinter as tk
        from tkinter import ttk
        from unittest.mock import patch
        from koei_editor.games.wo3u_ps3.editor import Editor
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.addCleanup(root.destroy)
        root.withdraw()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'copy.bin'
            native = os.environ.get('WO3U_PS3_US_COPIES')
            if native:
                original = Path(native.split(os.pathsep)[0])
                raw = original.read_bytes()
                context = original.with_name('PARAM.SFO').read_bytes()
            else:
                raw, context = fixture(), metadata()
            source.write_bytes(raw)
            source.with_name('PARAM.SFO').write_bytes(context)
            editor = Editor(root)
            with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                editor.open()
            editor.search.set('Precious stones')
            editor.refresh()
            self.assertEqual(editor.fields.get_children(), ('gems',))
            editor.fields.selection_set('gems')
            editor.value.set('456')
            editor.apply_selected()
            self.assertEqual(editor.changes, {'gems': 456})
            editor.review()
            editor.undo()
            self.assertEqual(editor.changes, {})
            dialog = next(child for child in root.winfo_children()
                          if isinstance(child, tk.Toplevel) and child.title() == 'Review Changes')
            export = next(child for child in dialog.winfo_children()
                          if isinstance(child, ttk.Button) and child.cget('text') == 'Export Review...')
            with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(source)), \
                 patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                export.invoke()
            errors.assert_not_called()
            report = json.loads(source.with_name(source.name + '.changes.json').read_text())
            self.assertEqual(report['game_id'], parser.GAME_ID)
            self.assertEqual(report['source_sha256'], editor.document.sha256)
            self.assertEqual(report['changes'], [{'field': 'gems',
                              'before': parser.field_map(editor.document)['gems'].value(raw), 'after': 456}])
            self.assertEqual(editor.changes, {})
            self.assertEqual(source.read_bytes(), raw)
            self.assertEqual(source.with_name('PARAM.SFO').read_bytes(), context)
            editor.max_visible()
            self.assertEqual(editor.changes, {})
            self.assertTrue(parser.inspection_rows(editor.document))
            editor.apply_theme('Dark')
            self.assertEqual(editor.theme_name.get(), 'Dark')
            editor.apply_theme('Light')
            self.assertEqual(editor.theme_name.get(), 'Light')
            editor.stage_values({'gems': 456})
            saved = Path(directory) / 'gui.bin'
            editor.save_to(saved)
            self.assertEqual(parser.field_map(parser.read_save(saved))['gems'].value(saved.read_bytes()), 456)
            self.assertEqual(source.read_bytes(), raw)
            self.assertTrue(editor.backup.exists())
            restored = Path(directory) / 'gui-restored.bin'
            with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(editor.backup)), \
                 patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(restored)):
                editor.restore()
            self.assertEqual(restored.read_bytes(), raw)
            self.assertEqual(source.read_bytes(), raw)
