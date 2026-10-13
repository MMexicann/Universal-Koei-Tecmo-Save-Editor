"""Registered Gust profiles keep the shared review/Undo/Max/safe-copy workflow."""
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.game_registry import get_game
from tests.test_firis_pc import fixture as firis_fixture
from tests.test_brsl_pc import fixture as brsl_fixture
from tests.test_ryza_pc import fixture as ryza_fixture


class NewGustProfileGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.withdraw();self.addCleanup(self.root.destroy)

    def test_registered_profiles_undo_review_max_exclusions_and_save_restore(self):
        for game_id,fixture in (('atelier_firis_pc',firis_fixture),
                                ('blue_reflection_second_light_pc',brsl_fixture),
                                ('atelier_ryza_pc',ryza_fixture)):
            with self.subTest(game=game_id),tempfile.TemporaryDirectory() as name:
                game = get_game(game_id);folder = Path(name)
                source = folder / ('source' + game.extension);raw = fixture();source.write_bytes(raw)
                host = tk.Frame(self.root);host.pack()
                editor = game.create_editor(self.root,host)
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename',return_value=str(source)), \
                        patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                    editor.open();errors.assert_not_called()
                    field = next(f for f in editor.adapter.fields_for(editor.document)
                                 if f.value(editor.document.payload) > f.minimum)
                    editor.group.set(field.group);editor.refresh()
                    editor.fields.selection_set(field.id);editor.value.set(str(field.minimum))
                    editor.apply_selected();self.assertEqual(editor.changes,{field.id:field.minimum})
                    editor.max_visible();self.assertEqual(editor.changes,{field.id:field.minimum})
                    editor.undo();self.assertEqual(editor.changes,{})
                    editor.fields.selection_set(field.id);editor.value.set(str(field.minimum))
                    editor.apply_selected();editor.review()
                    self.assertEqual(len(editor.adapter.review(editor.document,editor.changes)),1)
                    for child in self.root.winfo_children():
                        if isinstance(child,tk.Toplevel):child.destroy()
                    target = folder / ('edited' + game.extension);editor.save_to(target)
                    errors.assert_not_called()
                    self.assertEqual(source.read_bytes(),raw)
                    # A Second Light count of 1 becomes inspection-only after
                    # saving: verify the original stable native field directly.
                    self.assertEqual(field.value(editor.document.payload),field.minimum)
                    restored = editor.adapter.restore(editor.backup,folder / ('restored' + game.extension))
                    self.assertEqual(restored.read_bytes(),raw)
                    self.assertEqual(editor.changes,{})
                    tables = editor.presentation.inspection_tables(editor.document)
                    self.assertTrue(tables)
                host.destroy()
