"""Availability actions use the normal reviewed, undoable scalar workflow."""
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.game_registry import get_game
from koei_editor.games.dw6 import dw6_parser as pc
from koei_editor.games.dw6 import availability
from koei_editor.games.dw6_ps3 import parser as ps3
from tests.test_dw6_availability import fixture
from tests.test_dw6_ps3 import context


class DW6AvailabilityGuiTests(unittest.TestCase):
    def test_both_editors_enforce_prerequisites_stage_complete_batches_and_undo_before_safe_save(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(root.destroy)
        root.withdraw()
        for backend in (pc, ps3):
            with self.subTest(profile=backend.GAME_ID), tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                source = folder / ('APP.BIN' if backend is ps3 else 'save.dat')
                source.write_bytes(fixture(backend))
                if backend is ps3:
                    context(folder)
                host = tk.Frame(root)
                host.pack()
                editor = get_game(backend.GAME_ID).create_editor(root, host)
                self.assertIn('disabled', editor.more_unlocks.state())
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                    editor.open()
                self.assertNotIn('disabled', editor.more_unlocks.state())
                editor.group.set(availability.MUSOU_GROUP)
                editor.search.set('Xiahou Dun')
                editor.refresh()
                key = 'musou_0_available'
                self.assertIn(key, editor.fields.get_children())
                editor.fields.selection_set(key)
                editor.value.set('1')
                with patch('koei_editor.shared.verified_gui.messagebox.showerror') as error:
                    editor.apply_selected()
                error.assert_called_once()
                self.assertEqual(editor.changes, {})
                editor.unlock_musou()
                self.assertEqual(editor.changes['officer_0_unlocked'], 1)
                self.assertEqual(editor.changes[key], 1)
                editor.review()
                editor.undo()
                self.assertEqual(editor.changes, {})
                editor.unlock_stages()
                self.assertEqual(len(editor.changes), 23)
                self.assertTrue(all(key.startswith('stage_') for key in editor.changes))
                editor.undo()
                editor.unlock_musou()
                destination = folder / ('edited.bin' if backend is ps3 else 'edited.dat')
                with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(destination)):
                    editor.save_as()
                actual = backend.read_save(destination)
                self.assertEqual(backend.field_map(actual)['musou_0_available'].value(actual.payload), 1)
                self.assertEqual(backend.field_map(actual)['officer_0_unlocked'].value(actual.payload), 1)
                offset = backend.OFFICER_BASE + 41 * 168 + 900
                self.assertEqual(actual.raw[offset + 1:offset + 4], source.read_bytes()[offset + 1:offset + 4])
                self.assertEqual(source.read_bytes(), fixture(backend))
                host.destroy()
