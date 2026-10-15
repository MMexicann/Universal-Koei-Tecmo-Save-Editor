"""Registered new-game contracts and real Tk copied-save workflows."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.scalar_contract import ScalarContractTests
from tests.test_dw7xl_format import synthetic_raw as dw7_raw
from tests.test_wo3u_format import procedural_raw as wo3_raw
from tests.test_pw4_format import procedural_raw as pw4_raw


class DW7RegisteredContractTests(ScalarContractTests, unittest.TestCase):
    game_id = 'dw7xl'

    def fixture_bytes(self):
        return dw7_raw()


class WO3RegisteredContractTests(ScalarContractTests, unittest.TestCase):
    game_id = 'wo3u'

    def fixture_bytes(self):
        return wo3_raw()


class PW4RegisteredContractTests(ScalarContractTests, unittest.TestCase):
    game_id = 'pw4'
    # The first editable field lives in the profile object, whose native byte
    # sum is the only additional payload change for a Beli edit.
    payload_integrity_offsets = frozenset(range(0x6B3C, 0x6B40))

    def fixture_bytes(self):
        return pw4_raw()


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'A graphical display is required')
class NewGameGuiTests(unittest.TestCase):
    def test_dw7_registered_edit_switch_theme_review_backup_and_save(self):
        import tkinter as tk
        from tkinter import ttk
        from koei_editor.application import Application
        import koei_editor.games.dw7xl.dw7xl_parser as backend
        root = tk.Tk()
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as folder:
                folder = Path(folder)
                source = folder / 'copy.dat'
                raw = dw7_raw()
                source.write_bytes(raw)
                app = Application(root, preferences_path=folder / 'preferences.json')
                editor = app.select_game('dw7xl')
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                    editor.open()
                editor.search.set('Gold')
                self.assertEqual(editor.fields.get_children(), ('gold',))
                editor.fields.selection_set('gold')
                editor.value.set('12345')
                editor.apply_selected()
                self.assertEqual(editor.changes, {'gold': 12345})
                editor.undo()
                self.assertEqual(editor.changes, {})
                self.assertEqual(int(editor.value.get()),
                                 backend.field_map(editor.document)['gold'].value(editor.document.payload))
                editor.fields.selection_set('gold')
                editor.value.set('12345')
                editor.apply_selected()
                app.select_game('dw3')
                app.apply_theme('Dark')
                self.assertIs(app.select_game('dw7xl'), editor)
                self.assertEqual(editor.changes, {'gold': 12345})
                editor.review()
                review = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
                def descendants(widget):
                    for child in widget.winfo_children():
                        yield child
                        yield from descendants(child)
                tree = next(w for w in descendants(review) if isinstance(w, ttk.Treeview))
                self.assertEqual(len(tree.get_children()), 1)
                self.assertEqual(tree.item(tree.get_children()[0], 'values')[2], '12,345')
                review.destroy()
                target = folder / 'edited.dat'
                with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(target)), \
                     patch('koei_editor.shared.verified_gui.messagebox.showinfo'):
                    editor.save_as()
                result = backend.read_save(target)
                self.assertEqual(backend.field_map(result)['gold'].value(result.payload), 12345)
                self.assertEqual(source.read_bytes(), raw)
                self.assertEqual(editor.changes, {})
                backups = list((folder / 'UniversalEditorBackups').glob('*.dat'))
                self.assertTrue(backups)
                self.assertEqual(backups[0].read_bytes(), raw)
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
