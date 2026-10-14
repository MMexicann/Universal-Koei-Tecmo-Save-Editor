"""Actual queue workers, retained workspaces and reviewed-converter handoff."""

import json
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.application import Application
from koei_editor import conversion
from koei_editor.shared import batch_conversion as backend
from koei_editor.shared.batch_conversion_gui import BatchWorkspace
from tests.test_conversion import write_copy


class BatchGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.root.destroy)
        self.root.withdraw()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name).resolve()
        self.pc = write_copy(self.folder / "pc", "dw6")
        self.ps3 = write_copy(self.folder / "ps3", "dw6_ps3", 1)
        self.spec = backend.JobSpec(
            "copy-1", "dw6-to-dw6_ps3", self.pc, self.ps3, self.folder / "converted"
        )

    def finish(self, workspace):
        end = time.monotonic() + 10
        while workspace.busy and time.monotonic() < end:
            self.root.update()
            time.sleep(0.01)
        self.assertFalse(workspace.busy)

    def test_minimum_window_keeps_author_navigation_and_theme_visible_with_long_title(
        self,
    ):
        app = Application(self.root, persist_preferences=False)
        self.root.geometry("1080x820")
        self.root.deiconify()
        app.breadcrumb.set("Long game and exact platform/revision details " * 30)
        self.root.update()
        for control in (
            app.author_label,
            app.theme_selector,
            app.home_button,
            app.converter_button,
            app.compare_button,
            app.batch_button,
        ):
            self.assertTrue(control.winfo_ismapped())
            self.assertGreater(control.winfo_width(), 10)
            self.assertLessEqual(
                control.winfo_x() + control.winfo_width(), control.master.winfo_width()
            )
        self.assertGreater(app.breadcrumb_label.winfo_width(), 1)
        self.assertLessEqual(
            app.breadcrumb_label.winfo_x() + app.breadcrumb_label.winfo_width(),
            app.author_label.winfo_x(),
        )

    def test_review_export_progress_private_report_and_retry_existing_report(self):
        workspace = BatchWorkspace(self.root, self.root)
        workspace.specs = [self.spec]
        workspace.render()
        workspace.table.selection_set(self.spec.id)
        workspace.review()
        self.finish(workspace)
        workspace.show_scope()
        self.assertIn("roster", workspace.scope.get().lower())
        self.assertIn("Roster review:", workspace.scope_preview.get("1.0", "end"))
        self.assertEqual(str(workspace.scope_preview["state"]), "disabled")
        self.assertIsNotNone(workspace.prepared)
        workspace.export()
        self.finish(workspace)
        self.assertEqual(workspace.last_report["completed"], 1)
        self.assertIsNone(workspace.prepared)
        self.assertEqual(workspace.table.item(self.spec.id, "values")[-1], "Completed")
        destination = self.folder / "report.json"
        with patch(
            "koei_editor.shared.batch_conversion_gui.filedialog.asksaveasfilename",
            return_value=str(destination),
        ):
            workspace.save_report()
            self.finish(workspace)
        self.assertTrue(json.loads(destination.read_text(encoding="utf-8"))["success"])
        with (
            patch(
                "koei_editor.shared.batch_conversion_gui.filedialog.asksaveasfilename",
                return_value=str(destination),
            ),
            patch("koei_editor.shared.batch_conversion_gui.messagebox.showerror"),
        ):
            workspace.save_report()
            self.finish(workspace)
        self.assertIsNotNone(workspace.last_report)
        self.assertEqual(str(workspace.report_button["state"]), "normal")

    def test_converter_handoff_all_workspace_switching_and_busy_close(self):
        app = Application(self.root, persist_preferences=False)
        app.show_converter()
        converter = app.converter
        converter.prepared = conversion.prepare(self.spec.route, self.pc, self.ps3)
        with (
            patch(
                "koei_editor.shared.batch_conversion_gui.filedialog.askdirectory",
                return_value=str(self.folder),
            ),
            patch(
                "koei_editor.shared.batch_conversion_gui.simpledialog.askstring",
                return_value="converted",
            ),
        ):
            converter.queue_review()
        workspace = app.batch
        self.assertEqual(len(workspace.specs), 1)
        self.assertTrue(workspace.frame.winfo_manager())
        self.assertFalse(converter.frame.winfo_manager())
        workspace.review()
        self.finish(workspace)
        before = (app.platform_choice.get(), app.library_search.get())
        app.focus_library_search()
        self.assertEqual(before, (app.platform_choice.get(), app.library_search.get()))
        app.show_comparison()
        self.assertFalse(workspace.frame.winfo_manager())
        app.show_batch()
        self.assertFalse(app.comparison.frame.winfo_manager())
        self.assertIs(app.batch, workspace)
        app.select_game("dw6")
        self.assertFalse(workspace.frame.winfo_manager())
        app.show_converter()
        app.show_library()
        app.show_batch()
        self.assertIsNotNone(workspace.prepared)
        workspace.busy = True
        with (
            patch("tkinter.messagebox.showinfo") as info,
            patch.object(app.root, "destroy") as destroy,
        ):
            app.close()
            info.assert_called_once()
            destroy.assert_not_called()
        workspace.busy = False
        app.apply_theme("Dark")
        app.apply_theme("Light")

    def test_save_plan_retains_review_and_report_rechecks_changed_completed_output(
        self,
    ):
        workspace = BatchWorkspace(self.root, self.root)
        workspace.specs = [self.spec]
        workspace.render()
        workspace.review()
        self.finish(workspace)
        review = workspace.prepared
        plan = self.folder / "saved-plan.json"
        with patch(
            "koei_editor.shared.batch_conversion_gui.filedialog.asksaveasfilename",
            return_value=str(plan),
        ):
            workspace.save_plan()
            self.finish(workspace)
        self.assertEqual(backend.load_plan(plan), (self.spec,))
        self.assertIs(workspace.prepared, review)
        self.assertEqual(str(workspace.export_button["state"]), "normal")
        workspace.export()
        self.finish(workspace)
        (self.spec.output_dir / "APP.BIN").write_bytes(b"changed")
        report = self.folder / "stale-report.json"
        with (
            patch(
                "koei_editor.shared.batch_conversion_gui.filedialog.asksaveasfilename",
                return_value=str(report),
            ),
            patch("koei_editor.shared.batch_conversion_gui.messagebox.showerror"),
        ):
            workspace.save_report()
            self.finish(workspace)
        self.assertFalse(report.exists())

    def test_load_bounded_plan_remove_clear_and_preflight_error(self):
        workspace = BatchWorkspace(self.root, self.root)
        plan = self.folder / "plan.json"
        plan.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "jobs": [
                        dict(
                            id=self.spec.id,
                            route=self.spec.route,
                            source=str(self.pc),
                            template=str(self.ps3),
                            output_dir=str(self.spec.output_dir),
                        )
                    ],
                }
            )
        )
        with patch(
            "koei_editor.shared.batch_conversion_gui.filedialog.askopenfilename",
            return_value=str(plan),
        ):
            workspace.load()
            self.finish(workspace)
        self.assertEqual(len(workspace.specs), 1)
        self.ps3.write_bytes(b"changed")
        with patch(
            "koei_editor.shared.batch_conversion_gui.messagebox.showerror"
        ) as error:
            workspace.review()
            self.finish(workspace)
            self.assertTrue(error.called)
        self.assertIsNone(workspace.prepared)
        self.assertFalse(self.spec.output_dir.exists())
        workspace.table.selection_set(self.spec.id)
        workspace.remove()
        self.assertFalse(workspace.specs)
        workspace.specs = [self.spec]
        workspace.clear()
        self.assertFalse(workspace.specs)
