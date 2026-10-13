"""Actual Tk staged edit workflows for exact Sony resource/stat profiles."""
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.game_registry import get_game
from koei_editor.shared import verified_gui
from koei_editor.games.bladestorm_ps3 import parser as bladestorm
from koei_editor.games.pw3_ps3 import parser as pw3
from koei_editor.games.aot1_vita import parser as aot1
from tests.test_bladestorm_ps3 import fixture as bladestorm_fixture
from tests.test_pw3_ps3 import fixture as pw3_fixture
from tests.test_aot1_vita import fixture as aot1_fixture


class SonyProfileGUI(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.addCleanup(self.root.destroy)
        self.root.withdraw()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)

    def workflow(self, game_id, backend, raw, identity, key, search, value,
                 context_name='PARAM.SFO'):
        from importlib import import_module
        game = get_game(game_id)
        editor_type = import_module(game.editor_module).Editor
        editor = editor_type(self.root)
        source = self.folder / ('opened' + game.extension)
        source.write_bytes(raw)
        context = backend.identity_metadata(identity)
        companion = self.folder / context_name
        companion.parent.mkdir(parents=True, exist_ok=True)
        companion.write_bytes(context)
        with patch.object(verified_gui.filedialog, 'askopenfilename', return_value=str(source)), \
                patch.object(verified_gui.messagebox, 'showerror') as error:
            editor.open()
            error.assert_not_called()
        self.assertIsNotNone(editor.document)
        self.assertEqual(editor.adapter.game_id, game_id)
        self.assertTrue(editor.backup.exists())
        editor.search.set(search)
        editor.refresh()
        self.assertIn(key, editor.fields.get_children())
        editor.fields.selection_set(key)
        editor.value.set(str(value))
        editor.apply_selected()
        self.assertEqual(editor.changes, {key: value})
        editor.review()
        editor.undo()
        self.assertEqual(editor.changes, {})
        editor.max_visible()
        self.assertEqual(editor.changes, {})
        editor.show_inspector()
        self.root.update()
        editor.stage_values({key: value})
        destination = self.folder / ('edited' + game.extension)
        with patch.object(verified_gui.messagebox, 'showerror') as error:
            editor.save_to(destination)
            error.assert_not_called()
        reopened = game.get_scalar_adapter().read_save(destination)
        self.assertEqual(backend.field_map(reopened)[key].value(reopened.payload), value)
        self.assertEqual(source.read_bytes(), raw)
        self.assertEqual(companion.read_bytes(), context)
        self.assertEqual(editor.changes, {})

    def test_bladestorm_search_edit_review_undo_inspector_and_save(self):
        self.workflow('bladestorm_ps3', bladestorm, bladestorm_fixture(),
                      'BLES00113PLAY0', 'money', 'money', 123)

    def test_pw3_ps3_search_edit_review_undo_inspector_and_save(self):
        self.workflow('pw3_ps3', pw3, pw3_fixture(),
                      'NPEB02211-00', 'character_0_hp', 'Stored HP', 2500)

    def test_aot1_vita_search_edit_review_undo_inspector_and_save(self):
        self.workflow('aot1_vita', aot1, aot1_fixture(),
                      '/PCSB00898', 'money', 'Money', 123,
                      context_name='sce_sys/param.sfo')
