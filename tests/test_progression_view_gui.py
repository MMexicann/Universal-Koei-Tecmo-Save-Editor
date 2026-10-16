"""Vector cards are bounded, navigable and independent of save editing."""

import tkinter as tk
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import Mock

from koei_editor.shared.appearance import THEMES
from koei_editor.shared.progression import (
    DashboardCard, DashboardMetric, DashboardSection, ProgressionDashboard,
)
from koei_editor.shared.progression_view import (
    CARD_METRICS, DETAIL_PAGE_SIZE, PAGE_SIZE, ProgressionView,
)


def dashboard(count=70):
    characters = tuple(DashboardCard(
        f"character:{index}", f"Officer {index:03}", "Verified character record",
        tuple(DashboardMetric(
            f"metric:{index}:{stat}", f"Attribute {stat}", str(index + stat),
            field_id=f"field:{index}:{stat}" if stat % 2 == 0 else None,
            current=index if stat == 0 else None,
            total=100 if stat == 0 else None,
            note="Opened value",
        ) for stat in range(19)), search_text="officer character",
    ) for index in range(count))
    return ProgressionDashboard("Progression overview", (
        DashboardSection("characters", "Characters", characters, "Mapped officers only."),
        DashboardSection("resources", "Resources", (
            DashboardCard("resource:gold", "Treasury", metrics=(DashboardMetric("gold", "Gold", "42,000", field_id="gold"),)),
        ), "Resources are not completion."),
    ), "Read-only values from the opened save.")


class ProgressionViewGuiTests(TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.root.destroy)
        self.root.geometry("1180x820")
        self.navigate = Mock()
        self.snapshot = dashboard()
        self.view = ProgressionView(self.root, self.snapshot, on_navigate=self.navigate)
        self.view.pack(fill="both", expand=True)
        self.root.update()

    def test_large_inventory_paging_search_section_notes_and_selection(self):
        view = self.view
        self.assertEqual(len(view._visible_cards), PAGE_SIZE)
        self.assertEqual(len(view.card_selector["values"]), PAGE_SIZE)
        self.assertEqual(view._selected_id, "character:0")
        self.assertEqual(str(view.previous["state"]), "disabled")
        view.next.invoke()
        self.root.update()
        self.assertEqual(view._selected_id, f"character:{PAGE_SIZE}")
        self.assertEqual(view.page_text.get(), "Page 2 of 3")
        view.section.set("resources")
        self.root.update()
        self.assertEqual([card.id for card in view._visible_cards], ["resource:gold"])
        self.assertIn("Resources are not completion.", view.note_label["text"])
        view.section.set("characters")
        view.search.set("Officer 069")
        self.root.after(130, self.root.quit)
        self.root.mainloop()
        self.assertEqual([card.id for card in view._visible_cards], ["character:69"])
        self.assertEqual(view._selected_id, "character:69")
        view.search.set("unmapped phrase")
        self.root.after(130, self.root.quit)
        self.root.mainloop()
        self.assertEqual(view._visible_cards, ())
        self.assertEqual(str(view.detail_toggle["state"]), "disabled")
        self.assertIn("No matching", view.page_text.get())
        self.navigate.assert_not_called()
        self.assertEqual(self.snapshot, dashboard())

    def test_real_vector_metric_and_keyboard_details_reveal_only_mapped_fields(self):
        view = self.view
        item = view.canvas.find_withtag("card:character:0:metric:0")[0]
        x1, y1, x2, y2 = view.canvas.bbox(item)
        view.canvas.event_generate("<Motion>", x=(x1+x2)//2, y=(y1+y2)//2)
        view.canvas.event_generate("<Button-1>", x=(x1+x2)//2, y=(y1+y2)//2)
        self.root.update()
        self.navigate.assert_called_once_with("field:0:0")
        self.navigate.reset_mock()
        view.select_card("character:1")
        view.card_selector.current(2)
        view.card_selector.event_generate("<<ComboboxSelected>>")
        self.root.update()
        self.assertEqual(view._selected_id, "character:2")
        view._move_selection(1)
        self.assertEqual(view._selected_id, "character:3")
        view.detail_toggle.invoke()
        self.root.update()
        self.assertTrue(view.detail_metrics.winfo_ismapped())
        self.assertEqual(len(view.detail_metrics.winfo_children()), DETAIL_PAGE_SIZE)
        self.assertEqual([field_id for field_id, _ in view._metric_buttons], ["field:3:0", "field:3:2", "field:3:4"])
        view.detail_next.invoke()
        self.assertEqual(view.detail_page_text.get(), "Fields 2 / 4")
        view._metric_buttons[0][1].invoke()
        self.navigate.assert_called_once_with("field:3:6")
        self.assertEqual(self.snapshot, dashboard())

    def test_resize_theme_and_snapshot_refresh_preserve_search_and_selection(self):
        view = self.view
        self.assertGreaterEqual(view._columns, 3)
        view.select_card("character:3")
        view.section.set("characters")
        view.search.set("officer")
        self.root.after(130, self.root.quit)
        self.root.mainloop()
        for name, palette in THEMES.items():
            view.apply_theme(name)
            self.root.update()
            self.assertEqual(view.canvas["background"], palette["background"])
            self.assertEqual(view.detail_heading["foreground"], palette["text"])
            self.assertEqual(view._selected_id, "character:3")
        self.root.geometry("800x650")
        self.root.update()
        self.assertEqual(view._columns, 1)
        self.assertGreater(view.canvas.winfo_height(), 200)
        self.assertGreater(view.next.winfo_height(), 15)
        self.assertLess(view.next.winfo_rooty() + view.next.winfo_height(), self.root.winfo_rooty() + 650)
        self.assertEqual(view.card_selector.grid_info()["row"], 0)
        view.set_dashboard(dashboard(1000))
        self.root.update()
        self.assertEqual(view._selected_id, "character:3")
        self.assertEqual(view.search.get(), "officer")
        self.assertLess(len(view.canvas.find_all()), PAGE_SIZE * (CARD_METRICS * 6 + 10))
        self.assertEqual(len(view.card_selector["values"]), PAGE_SIZE)
        self.navigate.assert_not_called()

    def test_rail_scrolls_to_last_section_and_unknown_progress_has_no_bar(self):
        sections = tuple(DashboardSection(f"s{index}", f"Section {index}", (
            DashboardCard(f"card{index}", "Unknown range", metrics=(
                DashboardMetric("no-range", "Stored XP", "12345"),
                DashboardMetric("invalid-range", "Unusual opened level", "101", current=101, total=100),
                DashboardMetric("zero-range", "No denominator", "0", current=0, total=0),
            )),
        )) for index in range(40))
        self.view.set_dashboard(ProgressionDashboard("Mapped records", sections))
        self.root.update()
        self.assertFalse(self.view.canvas.find_withtag("progress-track"))
        self.view.rail.yview_moveto(1)
        self.root.update()
        self.assertGreater(self.view.rail.yview()[0], 0)
        self.view._section_buttons[-1][1].invoke()
        self.root.update()
        self.assertEqual(self.view._selected_id, "card39")
        self.assertEqual(len(self.view._visible_cards), 1)
        self.navigate.assert_not_called()

    def test_destroy_cancels_deferred_work_without_callback_errors(self):
        self.view.search.set("Officer")
        self.view._resize()
        self.view.destroy()
        self.root.update()
        self.navigate.assert_not_called()

    def test_filtering_retains_selected_record_on_its_actual_visible_page(self):
        self.view.select_card("character:50")
        self.view.search.set("Officer")
        self.root.after(130, self.root.quit)
        self.root.mainloop()
        self.assertEqual(self.view._page, 2)
        self.assertEqual(self.view._selected_id, "character:50")
        self.assertTrue(self.view.card_choice.get().endswith("Officer 050"))
        self.view.section.set("characters")
        self.view.section.set("All sections")
        self.assertEqual(self.view._page, 2)
        self.assertEqual(self.view._selected_id, "character:50")
        self.assertTrue(self.view.card_choice.get().endswith("Officer 050"))

    def test_long_opened_text_is_fully_copyable_without_expanding_the_dashboard(self):
        value = "A multiline opened value\n" * 100
        self.view.set_dashboard(ProgressionDashboard("Long values", (
            DashboardSection("text", "Text", (DashboardCard("long", "A very long title " * 100,
                metrics=(DashboardMetric("long-text", "Name", value, field_id="name"),)),)),
        )))
        self.view.detail_toggle.invoke()
        self.root.update()
        self.assertEqual(self.view._metric_value_entries[0].get(), value)
        self.assertEqual(self.view._metric_value_entries[0].instate(["readonly"]), True)
        self.assertLess(self.view.winfo_reqwidth(), 1300)
        self.assertLess(self.view.detail_heading.winfo_reqwidth(), self.root.winfo_width())
        self.view._metric_value_entries[0].delete(0, "end")
        self.assertEqual(self.view._metric_value_entries[0].get(), value)
        self.navigate.assert_not_called()

    def test_verified_near_full_fraction_never_rounds_up_to_completed(self):
        self.view.set_dashboard(ProgressionDashboard("Verified fractions", (
            DashboardSection("progress", "Progress", (DashboardCard("counts", "Mapped objectives",
                metrics=tuple(DashboardMetric(f"count-{current}", "Mapped count", str(current),
                    current=current, total=1000000) for current in (999999, 1, 1000000))),)),
        )))
        self.root.update()
        annotations = [self.view.canvas.itemcget(item, "text") for item in self.view.canvas.find_all()
                       if self.view.canvas.type(item) == "text"]
        self.assertIn("999,999 / 1,000,000  ·  <100%", annotations)
        self.assertIn("1 / 1,000,000  ·  <0.01%", annotations)
        self.assertIn("1,000,000 / 1,000,000  ·  100%", annotations)

    def test_real_application_dashboards_fit_both_themes_and_compact_viewports(self):
        from koei_editor.application import Application
        from tests.test_origins_parser import fixture
        from tests.test_verified_editors import synthetic_raw
        self.view.destroy()
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve()
            app = Application(self.root, preferences_path=folder / "prefs.json", persist_preferences=False)
            # The supported minimum is 1080x820. Also exercise a smaller desktop
            # to verify dashboard paging remains reachable under tight geometry.
            self.root.minsize(650, 500)
            for game_id in ("origins", "dw8xl"):
                source = folder / (game_id + ".dat")
                raw = fixture() if game_id == "origins" else synthetic_raw(game_id)
                source.write_bytes(raw)
                editor = app.select_game(game_id)
                self.assertTrue(editor.open_path(source))
                editor.workspace_tabs.select(editor.dashboard_page)
                for theme in THEMES:
                    app.apply_theme(theme)
                    for width, height in ((1080, 820), (800, 650)):
                        self.root.geometry(f"{width}x{height}")
                        self.root.update()
                        view = editor.dashboard_view
                        self.assertGreater(view.canvas.winfo_height(), 100)
                        self.assertLessEqual(view.next.winfo_rooty() + view.next.winfo_height(),
                                             self.root.winfo_rooty() + height)
                        view.detail_toggle.invoke()
                        self.root.update()
                        self.assertLess(view.detail_metrics.winfo_reqwidth(), width)
                        view.detail_toggle.invoke()
                        self.assertFalse(editor.changes)
                self.assertEqual(source.read_bytes(), raw)
