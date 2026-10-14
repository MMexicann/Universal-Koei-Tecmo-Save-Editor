"""Named DW6 equipment controls through actual retained scalar workspaces."""

from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.game_registry import get_game
from koei_editor.games.dw6 import dw6_parser as pc
from koei_editor.games.dw6_ps3 import parser as ps3
from tests.test_dw6_equipment import equipped_fixture
from tests.test_dw6_ps3 import context


class EquipmentGuiTests(unittest.TestCase):
    def test_both_platforms_named_search_choices_capacity_undo_review_safe_save(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(root.destroy)
        root.withdraw()
        for backend in (pc, ps3):
            with (
                self.subTest(profile=backend.GAME_ID),
                tempfile.TemporaryDirectory() as folder,
            ):
                host = tk.Frame(root)
                host.pack()
                source = Path(folder) / ("APP.BIN" if backend is ps3 else "save.dat")
                raw = equipped_fixture(backend)
                source.write_bytes(raw)
                if backend is ps3:
                    context(Path(folder))
                editor = get_game(backend.GAME_ID).create_editor(root, host)
                with patch(
                    "koei_editor.shared.verified_gui.filedialog.askopenfilename",
                    return_value=str(source),
                ):
                    editor.open()
                self.assertIsNotNone(editor.document)
                editor.group.set("Weapon skills")
                editor.search.set("Flash")
                editor.refresh()
                key = "officer_40_weapon_7_skill_9"
                self.assertIn(key, editor.fields.get_children())
                editor.fields.selection_set(key)
                editor.value.set("1")
                editor.apply_selected()
                self.assertEqual(editor.changes, {key: 1})
                editor.max_selected()
                self.assertEqual(editor.changes, {key: 1})
                editor.review()
                editor.undo()
                self.assertEqual(editor.changes, {})
                changes = {f"officer_40_weapon_7_skill_{bit}": 1 for bit in range(5)}
                editor.stage_values(changes)
                with patch(
                    "koei_editor.shared.verified_gui.messagebox.showerror"
                ) as error:
                    editor.stage_values({key: 1})
                error.assert_called_once()
                self.assertEqual(editor.changes, changes)
                editor.undo()
                editor.stage_values(
                    {key: 1, "officer_40_equipped_weapon": 7, "horse_0_skill_10": 1}
                )
                editor.apply_theme("Dark")
                editor.apply_theme("Light")
                destination = Path(folder) / (
                    "edited.bin" if backend is ps3 else "edited.dat"
                )
                with patch(
                    "koei_editor.shared.verified_gui.filedialog.asksaveasfilename",
                    return_value=str(destination),
                ):
                    editor.save_as()
                actual = backend.read_save(destination)
                self.assertEqual(
                    backend.field_map(actual)[key].value(actual.payload), 1
                )
                self.assertEqual(source.read_bytes(), raw)
                host.destroy()
