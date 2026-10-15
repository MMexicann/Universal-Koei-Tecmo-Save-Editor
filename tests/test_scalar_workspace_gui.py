"""Category navigation and compact controls preserve the retained edit session."""

from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.application import Application
from koei_editor.shared.appearance import THEMES
from tests.test_origins_parser import fixture


class ScalarWorkspaceGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.root.destroy)
        self.area = tempfile.TemporaryDirectory()
        self.addCleanup(self.area.cleanup)
        self.folder = Path(self.area.name)
        self.app = Application(
            self.root,
            preferences_path=self.folder / "prefs.json",
            persist_preferences=False,
        )
        self.root.geometry("1080x820")
        self.editor = self.app.select_game("origins")
        self.source = self.folder / "SLOT0000.dat"
        self.source.write_bytes(fixture())
        with (
            patch(
                "koei_editor.shared.verified_gui.filedialog.askopenfilename",
                return_value=str(self.source),
            ),
            patch("koei_editor.shared.verified_gui.messagebox.showerror") as errors,
        ):
            self.editor.open()
            errors.assert_not_called()
        self.root.update()

    def test_category_counts_pending_styles_and_undo_follow_real_edits(self):
        editor = self.editor
        self.assertEqual(
            editor.category_counts["All fields"],
            len(editor.adapter.fields_for(editor.document)),
        )
        category = next(
            key
            for key, group in editor._category_groups.items()
            if group == "Resources"
        )
        editor.categories.selection_set(category)
        self.root.update()
        self.assertEqual(editor.group.get(), "Resources")
        self.assertEqual(
            set(editor.fields.get_children()),
            {"gold", "skill_points", "dlc_skill_points"},
        )
        editor.fields.selection_set("gold")
        editor.value.set("1111")
        editor.apply_selected()
        self.root.update()
        self.assertEqual(editor.changes, {"gold": 1111})
        self.assertIn("pending", editor.fields.item("gold", "tags"))
        self.assertIn("*1", editor.categories.item(category, "text"))
        for theme in THEMES:
            self.app.apply_theme(theme)
            self.assertEqual(editor.changes, {"gold": 1111})
            self.assertEqual(
                str(editor.fields.tag_configure("pending", "background")),
                THEMES[theme]["hover"],
            )
        editor.undo()
        self.root.update()
        self.assertEqual(editor.changes, {})
        self.assertNotIn("pending", editor.fields.item("gold", "tags"))
        self.assertNotIn("*", editor.categories.item(category, "text"))

    def test_compact_layout_advanced_toggle_and_horizontal_scrolling(self):
        editor = self.editor
        self.assertFalse(editor.options_panel.winfo_ismapped())
        self.assertFalse(editor.details_label.winfo_ismapped())
        self.assertNotIn("storage", editor.fields["displaycolumns"])
        self.assertGreater(editor.fields.winfo_height(), 220)
        self.assertTrue(editor.field_horizontal_scroll.winfo_ismapped())
        editor.options_visible.set(True)
        editor.toggle_options()
        editor.details_visible.set(True)
        editor.toggle_details()
        self.root.update()
        self.assertTrue(editor.experimental_toggle.winfo_ismapped())
        self.assertTrue(editor.details_label.winfo_ismapped())
        self.assertIn("storage", editor.fields["displaycolumns"])
        self.assertFalse(editor.adapter.experimental)
        editor.options_visible.set(False)
        editor.toggle_options()
        self.root.update()
        self.assertFalse(editor.experimental_toggle.winfo_ismapped())
        self.assertFalse(editor.adapter.experimental)
        with patch(
            "koei_editor.shared.verified_gui.messagebox.askyesno", return_value=True
        ):
            editor.experimental_mode.set(True)
            editor.toggle_experimental()
        self.root.update()
        self.assertTrue(editor.adapter.experimental)
        self.assertTrue(editor.mode_banner.winfo_ismapped())
        self.assertIn("EXPERIMENTAL", editor.limit_status.get())
        self.assertFalse(editor.experimental_toggle.winfo_ismapped())
        editor.experimental_mode.set(False)
        editor.toggle_experimental()
        self.root.update()
        self.assertFalse(editor.mode_banner.winfo_ismapped())

    def test_search_keyboard_filters_and_library_switch_preserve_pending(self):
        editor = self.editor
        editor.stage_values({"gold": 999})
        editor.group.set("Resources")
        editor.pending_only.set(True)
        editor.search.set("gold")
        self.root.update()
        self.assertEqual(editor.fields.get_children(), ("gold",))
        platform = self.app.platform_choice.get()
        self.app.focus_library_search()
        self.root.update()
        self.assertIs(self.root.focus_get(), editor.search_entry)
        self.assertEqual(self.app.active_game, "origins")
        self.assertEqual(platform, self.app.platform_choice.get())
        editor.clear_field_filters()
        self.assertEqual(editor.search.get(), "")
        self.assertEqual(editor.group.get(), "All fields")
        self.assertFalse(editor.pending_only.get())
        self.assertEqual(editor.changes, {"gold": 999})
        self.app.show_library()
        self.assertIs(self.app.select_game("origins"), editor)
        self.assertEqual(editor.changes, {"gold": 999})
        self.assertEqual(self.source.read_bytes(), fixture())

    def test_open_session_selector_resumes_exact_edition_with_live_pending_count(self):
        self.editor.stage_values({"gold": 1234})
        self.app.select_game("dw6_ps3")
        self.root.update()
        self.assertTrue(self.app.session_bar.winfo_ismapped())
        self.assertEqual(len(self.app._session_labels), 2)
        label = next(
            label for label, key in self.app._session_labels.items() if key == "origins"
        )
        self.assertIn("[1 pending]", label)
        self.app.session_choice.set(label)
        self.app.resume_session()
        self.assertEqual(self.app.active_game, "origins")
        self.assertIs(self.app.sessions["origins"][1], self.editor)
        self.assertEqual(self.editor.changes, {"gold": 1234})
        self.editor.undo()
        self.assertFalse(
            any("[1 pending]" in label for label in self.app._session_labels)
        )
        self.assertEqual(self.source.read_bytes(), fixture())


if __name__ == "__main__":
    unittest.main()
