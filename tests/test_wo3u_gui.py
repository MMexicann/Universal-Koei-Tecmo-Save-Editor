"""Shared GUI workflow checks with generated WO3 data, never player saves."""
from pathlib import Path
import os
import tempfile
import tkinter as tk
from unittest.mock import patch
import unittest

from tests.test_wo3u_format import procedural_raw
from koei_editor.games.wo3u.wo3u_editor import Editor
import koei_editor.games.wo3u.wo3u_parser as parser


class WO3GuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.source = Path(self.folder.name) / 'copy.bin'
        self.raw = procedural_raw()
        self.source.write_bytes(self.raw)
        self.editor = Editor(self.root)
        self.errors = []
        error = patch('koei_editor.shared.verified_gui.messagebox.showerror', side_effect=lambda *args: self.errors.append(args))
        error.start()
        self.addCleanup(error.stop)
        with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(self.source)):
            self.editor.open()
        self.assertFalse(self.errors)
        self.assertEqual(self.editor.save_extension, '.bin')

    def test_search_apply_review_undo_and_save_as(self):
        editor = self.editor
        editor.group.set('Officers')
        editor.search.set('Officer 1 Attack')
        editor.refresh()
        self.assertTrue(editor.fields.exists('officer_0_attack'))
        editor.fields.selection_set('officer_0_attack')
        editor.value.set('500')
        editor.apply_selected()
        self.assertEqual(editor.changes, {'officer_0_attack': 500})
        editor.review()
        self.assertTrue(any(isinstance(child, tk.Toplevel) for child in self.root.winfo_children()))
        editor.undo()
        self.assertEqual(editor.changes, {})
        editor.stage_values({'officer_0_attack': 500})
        destination = Path(self.folder.name) / 'edited.bin'
        editor.save_to(destination)
        self.assertFalse(self.errors)
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertTrue(editor.backup.exists())
        edited = parser.read_save(destination)
        self.assertEqual(parser.field_map(edited)['officer_0_attack'].value(edited.payload), 500)

    def test_weapon_search_binary_attribute_and_inspector(self):
        editor = self.editor
        editor.group.set('Weapons')
        editor.search.set('Verity')
        editor.refresh()
        self.assertEqual(editor.fields.get_children(), ('weapon_0_rank_1',))
        editor.fields.selection_set('weapon_0_rank_1')
        editor.value.set('10')
        editor.apply_selected()
        self.assertEqual(len(self.errors), 1)
        self.assertEqual(editor.changes, {})
        editor.show_inspector()
        tables = editor.presentation.inspection_tables(editor.document)
        self.assertEqual([table.title for table in tables],
                         ['Progression', 'Weapons', 'Resources', 'Item inventory', 'Mount loadouts'])
        self.assertTrue(any('Verity' in str(row) for row in tables[1].rows))
        editor.apply_theme('Dark')
        editor.apply_theme('Light')


@unittest.skipUnless(os.environ.get('WO3U_SAVE_COPY'), 'Private native WO3 copy unavailable')
class NativeWO3ExpansionGuiTests(unittest.TestCase):
    def test_native_rank_reinforcement_review_undo_and_surgical_saved_copy(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.addCleanup(root.destroy)
        root.withdraw()
        original = Path(os.environ['WO3U_SAVE_COPY'])
        raw = original.read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'copy.bin'
            source.write_bytes(raw)
            editor = Editor(root)
            errors = []
            with patch('koei_editor.shared.verified_gui.messagebox.showerror',
                       side_effect=lambda *args: errors.append(args)):
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                    editor.open()
                field = next(field for field in parser.fields_for(editor.document)
                             if field.id.endswith('_reinforcement'))
                value = field.value(raw) - 1
                editor.group.set('Weapons')
                editor.search.set(field.id)
                editor.refresh()
                self.assertEqual(editor.fields.get_children(), (field.id,))
                editor.fields.selection_set(field.id)
                editor.value.set(str(value))
                editor.apply_selected()
                self.assertEqual(editor.changes, {field.id: value})
                editor.max_visible()
                self.assertEqual(editor.changes, {field.id: value})
                editor.review()
                editor.undo()
                self.assertEqual(editor.changes, {})
                rank = next(field for field in parser.fields_for(editor.document)
                            if '_rank_' in field.id and 'Attribute ID' in field.label)
                rank_value = max(1, min(rank.value(raw) - 1, 10))
                editor.stage_values({field.id: value, rank.id: rank_value})
                expected = parser.serialize(editor.document, editor.changes)
                destination = Path(folder) / 'edited.bin'
                editor.save_to(destination)
                self.assertEqual(parser.read_save(destination).raw, expected)
                self.assertEqual(source.read_bytes(), raw)
                self.assertEqual(editor.backup.read_bytes(), raw)
                editor.show_inspector()
            self.assertEqual(errors, [])
        self.assertEqual(original.read_bytes(), raw)
