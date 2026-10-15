"""Actual Tk workflows for the native original PC XIII city adapter."""
import os
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from koei_editor.application import Application
from koei_editor.games.rotk13 import parser
from tests.test_rotk13_format import procedural_raw


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


class ROTK13GuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def workflow(self, raw):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'campaign-copy.s13'
            source.write_bytes(raw)
            app = Application(self.root, preferences_path=folder / 'preferences.json')
            editor = app.select_game(parser.GAME_ID)
            errors = []
            with patch('koei_editor.shared.verified_gui.messagebox.showerror',
                       side_effect=lambda *args: errors.append(args)):
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename',
                           return_value=str(source)):
                    editor.open()
                self.assertIsNotNone(editor.document)
                self.assertEqual(editor.backup.read_bytes(), raw)
                field = parser.fields_for(editor.document)[0]
                original = field.value(editor.document.payload)
                value = original - 1 if original else 1
                editor.search.set(field.id)
                editor.refresh()
                self.assertEqual(editor.fields.get_children(), (field.id,))
                editor.fields.selection_set(field.id)
                editor.value.set(str(value))
                editor.apply_selected()
                self.assertEqual(editor.changes, {field.id: value})
                editor.max_selected()
                editor.max_visible()
                self.assertEqual(editor.changes, {field.id: value})
                editor.undo()
                self.assertEqual(editor.changes, {})
                self.assertEqual(int(editor.value.get()), original)
                editor.value.set(str(value))
                editor.apply_selected()
                app.select_game('dw3')
                app.apply_theme('Dark')
                self.assertIs(app.select_game(parser.GAME_ID), editor)
                self.assertEqual(editor.changes, {field.id: value})
                editor.review()
                review = next(widget for widget in self.root.winfo_children()
                              if isinstance(widget, tk.Toplevel))
                tree = next(widget for widget in descendants(review)
                            if isinstance(widget, ttk.Treeview))
                rows = tree.get_children()
                self.assertEqual(len(rows), 1)
                self.assertEqual(tree.item(rows[0], 'values')[1:],
                                 (f'{original:,}', f'{value:,}'))
                review.destroy()
                editor.show_inspector()
                self.assertTrue(editor.presentation.inspection_tables(editor.document))
                destination = folder / 'edited.s13'
                with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename',
                           return_value=str(destination)):
                    editor.save_as()
                self.assertEqual(editor.changes, {})
                self.assertEqual(source.read_bytes(), raw)
                reopened = parser.read_save(destination)
                self.assertEqual(parser.field_map(reopened)[field.id].value(reopened.payload), value)
                self.assertEqual(reopened.header, parser.decode(raw).header)
                restored = folder / 'restored.s13'
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename',
                           return_value=str(editor.backup)), \
                        patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename',
                              return_value=str(restored)):
                    editor.restore()
                self.assertEqual(restored.read_bytes(), raw)
                self.assertEqual(errors, [])
                editor.save_to(destination)
                self.assertEqual(len(errors), 1)
                self.assertEqual(destination.read_bytes(), reopened.raw)
                # A rejected file must preserve the existing session and must
                # never invoke another game's decoder.
                malformed = folder / 'foreign.s13'
                malformed.write_bytes(b'foreign game')
                snapshot = editor.document
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename',
                           return_value=str(malformed)), \
                        patch('koei_editor.shared.verified_editor.decode') as other_decoder:
                    editor.open()
                other_decoder.assert_not_called()
                self.assertIs(editor.document, snapshot)
                self.assertEqual(len(errors), 2)

    def test_procedural_search_undo_review_retained_session_safe_save_and_restore(self):
        self.workflow(procedural_raw())

    def test_optional_genuine_campaign_gui(self):
        directory = os.environ.get('ROTK13_SAVE_COPIES')
        if not directory:
            self.skipTest('ROTK13_SAVE_COPIES private native campaign folder not supplied.')
        paths = sorted(Path(directory).glob('*.s13'))
        self.assertTrue(paths, 'Supplied native campaign folder contains no .s13 copies.')
        self.workflow(paths[0].read_bytes())
