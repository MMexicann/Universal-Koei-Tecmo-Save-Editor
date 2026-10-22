"""Launcher integration checks for the mod workshop window."""

import os
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from koei_editor.application import Application
from koei_editor.shared.mod_workshop.project_manager import load_project


@unittest.skipUnless(os.name == "nt" or os.environ.get("DISPLAY"), "A graphical display is required.")
class ModWorkshopGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = Application(self.root, preferences_path=Path(self.temp.name) / "preferences.json")

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_library_button_opens_a_reusable_workshop_window(self):
        workshop = self.app.show_mod_workshop()
        self.root.update_idletasks()

        self.assertEqual(workshop.window.title(), "Koei Tecmo Mod Creation Workshop")
        self.assertEqual(
            [workshop.notebook.tab(tab, "text") for tab in workshop.notebook.tabs()],
            ["Project", "Replacements", "Dependencies", "Compatibility", "Package"],
        )
        self.assertIs(self.app.show_mod_workshop(), workshop)
        workshop.close()

    def test_compatibility_check_saves_edited_project_fields_first(self):
        workshop = self.app.show_mod_workshop()
        for key, value in {
            "mod_id": "demo.texture",
            "name": "Demo Texture",
            "version": "1.0.0",
            "author": "Creator",
            "game_id": "demo-game",
            "game_version": "1.0.0",
            "platform": "Windows PC",
            "license": "MIT",
        }.items():
            workshop.fields[key].set(value)
        workshop.description.insert("1.0", "A user authored replacement.")
        workshop.project_parent.set(self.temp.name)
        workshop.create_project()
        self.assertIsNotNone(workshop.project_dir)

        workshop.fields["name"].set("Edited before validation")
        workshop.context_fields["game_id"].set("different-game")
        workshop.run_compatibility_check()

        self.assertEqual(load_project(workshop.project_dir).name, "Edited before validation")
        self.assertFalse(workshop.last_validation["valid"])
        self.assertIn(
            "compatibility.game.mismatch",
            {finding["code"] for finding in workshop.last_validation["findings"]},
        )
        workshop.close()


if __name__ == "__main__":
    unittest.main()
