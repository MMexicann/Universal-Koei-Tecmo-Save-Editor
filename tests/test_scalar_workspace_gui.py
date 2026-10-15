"""Category navigation and compact controls preserve the retained edit session."""

import json
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
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
        # A real Ctrl+F starts in the active app. Windows need not activate a
        # newly mapped test window; establish that keyboard precondition here.
        self.root.focus_force()
        self.root.update()
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

    def test_mixed_selection_requires_a_deliberate_value_and_clears_stale_controls(self):
        editor = self.editor
        editor.fields.selection_set(('gold', 'skill_points'))
        editor.selected()
        self.assertEqual(editor.value.get(), '')
        self.assertIn('2 selected fields; mixed current values', editor.selection_info.get())
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as error:
            editor.apply_selected()
        error.assert_called_once()
        self.assertEqual(editor.changes, {})
        editor.value.set('77')
        editor.apply_selected()
        self.assertEqual(editor.changes, {'gold': 77, 'skill_points': 77})
        self.assertEqual(editor.value.get(), '77')
        editor.fields.selection_set('gold')
        editor.selected()
        self.assertIn('Opened: 3,456; current: 77', editor.selection_info.get())
        editor.fields.selection_remove(editor.fields.selection())
        editor.selected()
        self.assertEqual(editor.value.get(), '')
        self.assertEqual(editor.choice_value.get(), '')
        editor.undo()
        self.assertEqual(editor.changes, {})
        self.assertEqual(self.source.read_bytes(), fixture())

    def test_review_search_keeps_the_complete_frozen_export(self):
        editor = self.editor
        editor.stage_values({'gold': 1234, 'skill_points': 88})
        editor.review()
        dialog = next(child for child in self.root.winfo_children()
                      if isinstance(child, tk.Toplevel) and child.title() == 'Review Changes')
        tree = dialog.review_tree
        self.assertEqual(len(tree.get_children()), 2)
        dialog.review_query.set('gold 1234')
        self.assertEqual(len(tree.get_children()), 1)
        self.assertEqual(tree.item(tree.get_children()[0], 'values'), ('Gold', '3,456', '1,234'))
        dialog.review_query.set('skill_points')
        self.assertEqual(len(tree.get_children()), 1)
        self.assertEqual(tree.item(tree.get_children()[0], 'values')[-1], '88')
        # The review describes the state when it opened. Filtering and later
        # staging must never silently narrow or rewrite its exported review.
        editor.stage_values({'gold': 999})
        destination = self.folder / 'frozen.changes.json'
        export = next(child for child in dialog.winfo_children()
                      if isinstance(child, ttk.Button) and child.cget('text') == 'Export Review...')
        with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename',
                   return_value=str(destination)):
            export.invoke()
        report = json.loads(destination.read_text())
        self.assertEqual({item['field']: item['after'] for item in report['changes']},
                         {'gold': 1234, 'skill_points': 88})
        dialog.review_query.set('')
        self.assertEqual(len(tree.get_children()), 2)
        self.assertEqual(self.source.read_bytes(), fixture())

    def test_inventory_choice_search_preserves_native_reference_and_undo(self):
        from koei_editor.games.sw4ii import sw4ii_parser as backend
        from tests.test_sw4ii_format import procedural_raw, seal

        # Generated occupied records exercise the real adapter's source-owned
        # mount choices. This is a GUI regression, not an in-game fixture.
        original = backend.decode(procedural_raw())
        payload = bytearray(original.payload)
        for index in range(backend.MOUNT_COUNT):
            base = backend.MOUNT_BASE + index * backend.MOUNT_STRIDE
            payload[base] = 0
            payload[base + 3:base + 5] = bytes((12, 25))
            payload[base + 0xA:base + 0xD] = bytes((20, 23, 27))
        payload[backend.OFFICER_BASE + 0x3D] = 0
        raw = seal(payload, original.seed)
        source = self.folder / 'mounts.dat'
        source.write_bytes(raw)
        editor = self.app.select_game('sw4ii')
        with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
            editor.open()
        editor.group.set('Mount equipment')
        editor.refresh()
        editor.fields.selection_set('officer_0_equipped_mount')
        editor.selected()
        self.root.update()
        self.assertTrue(editor.choice_tools.winfo_ismapped())
        self.assertEqual(len(editor.value_choice.cget('values')), 20)
        editor.choice_search.set('slot 17')
        choices = editor.value_choice.cget('values')
        self.assertEqual(len(choices), 1)
        self.assertEqual(editor._choice_values[choices[0]], 17)
        self.assertEqual(editor.value.get(), '0')
        self.assertEqual(editor.changes, {})
        editor.choice_value.set(choices[0])
        editor.selected_choice()
        editor.apply_selected()
        self.assertEqual(editor.changes, {'officer_0_equipped_mount': 17})
        editor.choice_search.set('no matching inventory')
        self.assertEqual(editor.value_choice.cget('values'), '')
        self.assertEqual(editor.value.get(), '17')
        editor.clear_choice_search()
        self.assertEqual(len(editor.value_choice.cget('values')), 20)
        editor.review()
        dialog = next(child for child in self.root.winfo_children()
                      if isinstance(child, tk.Toplevel) and child.title() == 'Review Changes')
        dialog.review_query.set('mount slot 17')
        self.assertEqual(len(dialog.review_tree.get_children()), 1)
        editor.undo()
        self.assertEqual(editor.changes, {})
        self.assertEqual(source.read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
