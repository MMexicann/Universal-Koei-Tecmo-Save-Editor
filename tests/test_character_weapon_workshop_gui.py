"""The Workshop edits portable plans in memory and delegates staging to editor."""

from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from koei_editor.shared import build_workshop
from koei_editor.shared.build_workshop_gui import BuildWorkshopView


def plans():
    base = build_workshop.BuildPlan(
        "dw3", "pc", "4", "Opened build",
        {"attack": 100, "defense": 75, "weapon_skill": "A"},
        {"primary_weapon": 12, "accessory": 2},
    )
    comparison = build_workshop.BuildPlan(
        "dw3", "pc", "4", "Heavy weapon",
        {"attack": 130, "defense": 75, "weapon_skill": "B"},
        {"primary_weapon": 15, "accessory": 2},
    )
    return base, comparison


def metadata():
    return {
        "attack": {"label": "Attack", "category": "stat", "character_id": "4",
                   "current_value": 100, "value_type": "integer", "evidence": "Mapped officer field"},
        "defense": {"label": "Defense", "category": "stat", "character_id": "4",
                    "current_value": 75, "value_type": "integer"},
        "weapon_skill": {"label": "Weapon skill", "category": "weapon", "character_id": "4",
                         "current_value": "A", "value_type": "string"},
        "primary_weapon": {"label": "Primary weapon", "category": "equipment", "character_id": "4",
                           "current_value": 12, "value_type": "integer",
                           "choices": ((12, "Sword"), (15, "Spear")),
                           "evidence": "Existing weapon choice mapping"},
        "accessory": {"label": "Accessory", "category": "equipment", "character_id": "4",
                      "current_value": 2, "choices": ((2, "Charm"),)},
    }


class BuildWorkshopGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.root.destroy)
        self.root.withdraw()
        self.original, self.other = plans()
        self.stage = Mock()
        self.view = BuildWorkshopView(
            self.root, game_id="dw3", platform_id="pc", plans=(self.original, self.other),
            field_metadata=metadata(), verified_stats=(
                {"character_id": "4", "label": "Verified attack total", "value": "180",
                 "evidence": "Current mapped DW3 progression projection", "formula": "provider-supplied"},
            ), on_stage=self.stage,
        )
        self.view.pack(fill="both", expand=True)
        self.root.update()

    def test_verified_stats_and_comparison_are_distinct_and_read_only_until_staging(self):
        stat = self.view.stats_tree.item("stat:0")
        self.assertEqual(stat["text"], "Verified attack total")
        self.assertIn("provider-supplied", stat["values"][1])
        attack = self.view.compare_tree.item("compare:0")
        self.assertEqual(attack["text"], "Attack")
        self.assertEqual(str(attack["values"][-1]), "-30")
        self.assertIn("not a gameplay formula", self.view.compare_note.get())
        self.stage.assert_not_called()
        self.assertEqual(self.original.values["attack"], 100)
        self.assertEqual(self.view.selected_plan.values["attack"], 100)

        self.view.stage_button.invoke()
        self.stage.assert_called_once_with(self.original)
        # Staging is only an injected callback. The Workshop has no writer.
        self.assertEqual(self.original.values["attack"], 100)

    def test_planned_value_edit_is_in_memory_and_comparison_delta_updates(self):
        self.assertTrue(self.view.edit_value("values", "attack", "140"))
        self.root.update()
        updated = self.view.selected_plan
        self.assertEqual(updated.values["attack"], 140)
        self.assertIs(type(updated.values["attack"]), int)
        self.assertEqual(self.original.values["attack"], 100)
        attack_rows = [row for row, key in self.view._row_keys.items()
                       if key == ("values", "attack")]
        self.assertEqual(len(attack_rows), 1)
        self.assertEqual(str(self.view.plan_tree.item(attack_rows[0], "values")[2]), "140")
        self.assertEqual(str(self.view.compare_tree.item("compare:0", "values")[-1]), "10")
        self.stage.assert_not_called()

    def test_equipment_uses_only_provider_choices_and_plan_export_roundtrips(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        with patch("koei_editor.shared.build_workshop_gui.filedialog.asksaveasfilename",
                   return_value=str(Path(self.folder.name) / "warrior")):
            self.assertTrue(self.view.export_plan())
        exported = Path(self.folder.name) / "warrior.build.json"
        saved = build_workshop.load_plan(exported)
        self.assertEqual(saved, self.original)
        self.assertEqual(saved.equipment["primary_weapon"], 12)
        self.stage.assert_not_called()

        self.view._store_value("equipment", "primary_weapon", 15)
        self.assertEqual(self.view.selected_plan.equipment["primary_weapon"], 15)
        self.assertEqual(self.original.equipment["primary_weapon"], 12)

    def test_import_rejects_another_game_without_replacing_current_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "other.build.json"
            other_game = build_workshop.BuildPlan(
                "samurai4", "pc", "4", "Other game", {"attack": 1}, {},
            )
            build_workshop.save_plan(other_game, path)
            with patch("koei_editor.shared.build_workshop_gui.messagebox.showerror") as errors:
                self.assertFalse(self.view.load_plan(path))
            errors.assert_called_once()
        self.assertIs(self.view.selected_plan, self.original)
        self.assertEqual(len(self.view._plans), 2)
        self.stage.assert_not_called()

    def test_editing_choice_uses_native_value_pair_without_relabeling_it(self):
        self.assertTrue(self.view._store_value("equipment", "primary_weapon", 15))
        self.assertEqual(self.view.selected_plan.equipment["primary_weapon"], 15)
        iid = next(row for row, key in self.view._row_keys.items()
                   if key == ("equipment", "primary_weapon"))
        values = self.view.plan_tree.item(iid, "values")
        self.assertEqual(values[2], "Spear (15)")
        self.assertEqual(values[3], "Existing weapon choice mapping")

    def test_provider_refresh_preserves_edited_imported_and_duplicated_plans(self):
        self.assertTrue(self.view.edit_value("values", "attack", "140"))
        edited = self.view.selected_plan
        with tempfile.TemporaryDirectory() as folder:
            imported = build_workshop.BuildPlan(
                "dw3", "pc", "4", "Imported plan", {"attack": 115},
                {"primary_weapon": 15},
            )
            path = Path(folder) / "imported.build.json"
            build_workshop.save_plan(imported, path)
            self.assertTrue(self.view.load_plan(path))
            imported_plan = self.view.selected_plan
            with patch("koei_editor.shared.build_workshop_gui.simpledialog.askstring",
                       return_value="Imported duplicate"):
                self.assertTrue(self.view.duplicate_plan())
            duplicated = self.view.selected_plan
            self.assertEqual(duplicated.name, "Imported duplicate")

        fresh = build_workshop.BuildPlan(
            "dw3", "pc", "4", "Opened build",
            {"attack": 100, "defense": 75, "weapon_skill": "A"},
            {"primary_weapon": 12, "accessory": 2},
        )
        self.view.set_provider_data((fresh,), metadata(), ())
        self.assertEqual(len(self.view._plans), 4)
        self.assertIn(edited, self.view._plans)
        self.assertIn(imported_plan, self.view._plans)
        self.assertIn(duplicated, self.view._plans)
        self.assertIs(self.view.selected_plan, duplicated)
        self.assertEqual(self.view.selected_plan.values["attack"], 115)

    def test_mapped_weapon_records_are_compared_in_the_read_only_weapon_tab(self):
        from koei_editor.games.dw8xl import workshop as dw8_workshop
        from koei_editor.shared import verified_editor
        from tests.test_dw8_weapon_order import procedural_equipment

        document = verified_editor.decode(procedural_equipment(), "dw8xl")
        comparison = BuildWorkshopView(
            self.root, game_id="dw8xl", platform_id="windows_pc",
            on_compare_records=lambda left, right: dw8_workshop.compare_weapon_records(
                document, left, right),
            record_options=dw8_workshop.weapon_record_options(document),
        )
        self.addCleanup(comparison.destroy)
        comparison.pack(fill="both", expand=True)
        self.root.update()
        attack = next(row for row in comparison.record_tree.get_children()
                      if comparison.record_tree.item(row, "text") == "Stored attack")
        self.assertEqual(comparison.record_tree.item(attack, "values")[:3], ("70", "70", "0"))
        self.assertIn("not a combat-damage formula", comparison.record_note.get())


if __name__ == "__main__":
    unittest.main()
