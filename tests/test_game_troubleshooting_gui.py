"""Retained UI tests for deterministic, path-private game diagnostics."""

import json
import os
from pathlib import Path
import tempfile
import threading
import tkinter as tk
import time
import unittest
from unittest.mock import patch

from koei_editor.application import Application
from koei_editor.shared.appearance import THEMES
from koei_editor.shared.game_troubleshooting import (
    TroubleshootingFinding,
    TroubleshootingReport,
)
from koei_editor.shared.game_troubleshooting_gui import (
    TroubleshootingWorkspace,
    export_json_report,
)


def sample_report():
    return TroubleshootingReport(
        game_id="origins",
        title="DYNASTY WARRIORS: ORIGINS",
        platform="Windows PC",
        ruleset_version="2026.10.22",
        findings=(
            TroubleshootingFinding(
                "installation.selected_root", "installation", "passed", "info",
                "Installation folder is readable",
                "The selected folder is accessible; game binaries were not validated.",
                ("12 ordinary files found",),
                "Use the official client if you choose to check game files.",
            ),
            TroubleshootingFinding(
                "configuration.syntax", "configuration", "warning", "warning",
                "A configuration file may have a syntax problem",
                "Basic syntax parsing failed; game-specific settings were not assessed.",
                ("1 INI file observed",),
                "Review the game's documentation before making any manual change.",
            ),
            TroubleshootingFinding(
                "mods.conflicts", "mods", "not_checked", "info",
                "Mod conflicts not established",
                "No reviewed per-title conflict map is available.", (),
                "Check each mod's documented compatibility notes.",
            ),
            TroubleshootingFinding(
                "prerequisites.reviewed_rules", "prerequisites", "not_checked", "info",
                "Prerequisites not assessed",
                "No reviewed prerequisite checklist is available.", (),
                "Check the game's official system requirements.",
            ),
            TroubleshootingFinding(
                "compatibility.reviewed_notes", "compatibility", "not_checked", "info",
                "No reviewed compatibility notes available",
                "No title-specific compatibility issue is recorded.", (),
                "Check the game's official update history.",
            ),
        ),
    )


class GameTroubleshootingExportTests(unittest.TestCase):
    def test_export_bytes_are_deterministic_and_exclude_local_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            output = export_json_report(sample_report(), folder / "report.json")
            expected = sample_report().to_json().encode("utf-8")
            self.assertEqual(output.read_bytes(), expected)
            self.assertNotIn(str(folder).encode(), output.read_bytes())
            self.assertNotIn(b"timestamp", output.read_bytes())
            self.assertEqual(export_json_report(sample_report(), folder / "second.json").read_bytes(), expected)

    def test_export_requires_new_json_destination_and_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            existing = folder / "report.json"
            existing.write_bytes(b"keep this file")
            with self.assertRaises(FileExistsError):
                export_json_report(sample_report(), existing)
            with self.assertRaises(ValueError):
                export_json_report(sample_report(), folder / "report.txt")
            self.assertEqual(existing.read_bytes(), b"keep this file")

    def test_export_never_reads_or_removes_a_concurrent_destination_replacement(self):
        for linked in (False, True):
            with self.subTest(symbolic_link=linked), tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                destination = folder / "report.json"
                foreign = folder / "private.txt"
                foreign.write_bytes(b"SYNTHETIC_PRIVATE_CONTENT")
                original_fsync, original_read = os.fsync, Path.read_bytes

                def replace_destination(descriptor):
                    original_fsync(descriptor)
                    destination.unlink(missing_ok=True)
                    if linked:
                        try:
                            destination.symlink_to(foreign)
                        except OSError:
                            self.skipTest("File symlinks unavailable")
                    else:
                        destination.write_bytes(b"FOREIGN_REPLACEMENT")

                def forbid_foreign_read(path):
                    if path == destination or path.resolve() == foreign:
                        raise AssertionError("Concurrent destination content must not be read")
                    return original_read(path)

                with patch("os.fsync", replace_destination), patch.object(Path, "read_bytes", forbid_foreign_read):
                    with self.assertRaises(FileExistsError):
                        export_json_report(sample_report(), destination)
                self.assertEqual(foreign.read_bytes(), b"SYNTHETIC_PRIVATE_CONTENT")
                self.assertEqual(destination.read_bytes(),
                                 b"SYNTHETIC_PRIVATE_CONTENT" if linked else b"FOREIGN_REPLACEMENT")
                self.assertEqual(destination.is_symlink(), linked)



class TroubleshootingWorkspaceLifecycleTests(unittest.TestCase):
    def test_close_is_idempotent_and_only_cancels_the_pending_poll(self):
        class Root:
            def __init__(self):
                self.cancelled = []

            def after_cancel(self, callback_id):
                self.cancelled.append(callback_id)

        workspace = object.__new__(TroubleshootingWorkspace)
        workspace._closed = False
        workspace._poll_id = "poll-1"
        workspace.root = Root()

        workspace.close()
        workspace.close()

        self.assertTrue(workspace._closed)
        self.assertIsNone(workspace._poll_id)
        self.assertEqual(workspace.root.cancelled, ["poll-1"])


class GameTroubleshootingGuiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self._destroy_root)
        self.app = Application(
            self.root,
            preferences_path=self.folder / "preferences.json",
            persist_preferences=False,
        )
        self.root.geometry("1080x820")
        self.root.update()

    def _destroy_root(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def finish(self, workspace):
        deadline = time.monotonic() + 10
        while workspace.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertFalse(workspace.busy, "Troubleshooting scan did not finish.")
        self.root.update()

    def center(self):
        return self.app.show_troubleshooting()

    def scan_with(self, workspace, report=None):
        report = report or sample_report()
        with patch(
            "koei_editor.shared.game_troubleshooting_gui.diagnose_game",
            return_value=report,
        ) as diagnose:
            workspace.game.set(workspace._game_labels["origins"])
            workspace.scan()
            self.finish(workspace)
        diagnose.assert_called_once()
        return report

    def test_workspace_is_lazy_and_scan_receives_only_explicit_folder_selections(self):
        installation = self.folder / "installation"
        configuration = self.folder / "configuration"
        mods = self.folder / "mods"
        installation.mkdir()
        configuration.mkdir()
        mods.mkdir()
        ini = configuration / "settings.ini"
        ini.write_text("[private]\npassword=do-not-export\n", encoding="utf-8")
        before = ini.read_bytes()
        workspace = self.center()
        self.assertFalse(workspace.busy)
        self.assertIsNone(workspace.report)

        with patch(
            "koei_editor.shared.game_troubleshooting_gui.diagnose_game",
            return_value=sample_report(),
        ) as diagnose:
            workspace.game.set(workspace._game_labels["origins"])
            workspace.installation_path.set(str(installation))
            workspace.config_path.set(str(configuration))
            workspace.mods_path.set(str(mods))
            workspace.scan()
            self.finish(workspace)
        diagnose.assert_called_once_with(
            "origins",
            installation_path=str(installation),
            config_path=str(configuration),
            mods_path=str(mods),
        )
        serialized = workspace.report.to_json()
        for private in (str(installation), str(configuration), str(mods), "do-not-export"):
            self.assertNotIn(private, serialized)
        self.assertEqual(ini.read_bytes(), before)
        self.assertEqual(workspace.preview.get("1.0", "end-1c"), serialized.rstrip("\n"))
        self.assertEqual(str(workspace.preview["state"]), "disabled")
        self.assertIn("2026.10.22", workspace.audit_key.get())
        self.assertIn("installation.selected_root", serialized)

        workspace.config_path.set(str(self.folder / "new-config"))
        self.assertIsNone(workspace.report)
        self.assertEqual(workspace.preview.get("1.0", "end-1c"), "")
        self.assertEqual(str(workspace.export_button["state"]), "disabled")

    def test_report_export_is_deterministic_private_and_never_overwrites(self):
        workspace = self.center()
        report = self.scan_with(workspace)
        destination = self.folder / "report.json"
        with patch(
            "koei_editor.shared.game_troubleshooting_gui.filedialog.asksaveasfilename",
            return_value=str(destination),
        ):
            workspace.export()
        expected = report.to_json().encode("utf-8")
        self.assertEqual(destination.read_bytes(), expected)
        payload = json.loads(destination.read_bytes())
        self.assertEqual(payload["schema"], "koei-game-troubleshooting")
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["ruleset_version"], "2026.10.22")
        self.assertNotIn("timestamp", payload)
        self.assertNotIn(str(self.folder), destination.read_text(encoding="utf-8"))

        previous = destination.read_bytes()
        with (
            patch(
                "koei_editor.shared.game_troubleshooting_gui.filedialog.asksaveasfilename",
                return_value=str(destination),
            ),
            patch("koei_editor.shared.game_troubleshooting_gui.messagebox.showerror") as error,
        ):
            workspace.export()
        error.assert_called_once()
        self.assertEqual(destination.read_bytes(), previous)

    def test_application_routes_retain_report_and_propagate_language_theme_and_text_size(self):
        workspace = self.center()
        report = self.scan_with(workspace)
        serialized = workspace.report.to_json()
        self.app.show_library()
        self.assertIs(self.app.execute_command("tool:troubleshooting"), workspace)
        self.assertIs(workspace.report, report)
        self.assertIn(workspace, self.app._tool_workspaces())
        self.assertEqual(self.app.breadcrumb.get(), self.app.tr("troubleshooting"))
        self.assertIn(
            "tool:troubleshooting",
            {entry.id for entry in self.app.command_entries()},
        )

        self.app.language_choice.set("Deutsch")
        self.app.change_language()
        self.assertEqual(workspace.language, "de")
        self.assertEqual(workspace.report.to_json(), serialized)
        self.assertIn("Prüfschlüssel", workspace.audit_key.get())
        self.assertIn("Voraussetzungen", [
            child.cget("text") for child in workspace.findings_frame.winfo_children()
        ])
        self.assertEqual(self.app.breadcrumb.get(), self.app.tr("troubleshooting"))

        self.app.apply_theme("Dark")
        self.app.text_size_choice.set("140%")
        self.app.change_text_size()
        self.root.update()
        self.assertEqual(workspace.preview.cget("background"), THEMES["Dark"]["surface"])
        from tkinter import font
        self.assertEqual(font.Font(self.root, font=workspace.preview.cget("font")).actual("size"), 14)

    def test_search_fields_is_consumed_when_troubleshooting_is_visible(self):
        workspace = self.center()
        self.root.focus_force()
        with patch.object(self.app, "show_platform") as show_platform:
            self.root.event_generate("<Control-f>")
            self.root.update()
            self.assertEqual(self.app.focus_library_search(), "break")
            self.assertEqual(self.app.execute_command("command:search_fields"), "break")
        show_platform.assert_not_called()
        self.assertTrue(workspace.frame.winfo_ismapped())
        self.assertFalse(self.app.library.winfo_ismapped())
        self.assertIsNot(self.root.focus_get(), self.app.library_search_entry)

    def test_versions_help_coexists_with_troubleshooting_report_and_lifecycle(self):
        from tkinter import font
        from koei_editor.shared.help_center import HelpCenter

        workspace = self.center()
        report = self.scan_with(workspace)
        self.assertEqual(self.app.show_help("versions"), "break")
        versions = self.app.help_center
        self.assertIsInstance(versions, HelpCenter)
        self.assertEqual(versions.selected_tab(), "versions")
        panel = versions._panels["versions"]
        self.assertIs(self.app.execute_command("tool:troubleshooting"), workspace)
        self.assertIs(workspace.report, report)
        self.app.language_choice.set("Deutsch")
        self.app.change_language()
        self.assertEqual(versions.language, "de")
        self.assertEqual(panel.language, "de")
        self.assertEqual(workspace.language, "de")
        self.assertEqual(self.app.breadcrumb.get(), self.app.tr("troubleshooting"))
        self.app.apply_theme("Dark")
        self.app.text_size_choice.set("140%")
        self.app.change_text_size()
        self.root.update()
        for text in (workspace.preview, panel.build_detail):
            self.assertEqual(text.cget("background"), THEMES["Dark"]["surface"])
            self.assertEqual(font.Font(self.root, font=text.cget("font")).actual("size"), 14)
        self.assertEqual(self.app.show_help("versions"), "break")
        self.assertIs(self.app.help_center, versions)
        self.assertEqual(versions.selected_tab(), "versions")
        self.root.update()
        self.assertTrue(versions.frame.winfo_ismapped())
        self.assertFalse(workspace.frame.winfo_ismapped())

    def test_scan_errors_do_not_expose_exception_paths_or_values(self):
        workspace = self.center()
        workspace.game.set(workspace._game_labels["origins"])
        secret = str(self.folder / "private-path")
        with patch(
            "koei_editor.shared.game_troubleshooting_gui.diagnose_game",
            side_effect=RuntimeError(secret),
        ):
            workspace.scan()
            self.finish(workspace)
        self.assertIsNone(workspace.report)
        self.assertNotIn(secret, workspace.status.get())
        self.assertNotIn(secret, workspace.preview.get("1.0", "end"))

    def test_application_shutdown_proceeds_while_read_only_scan_worker_is_pending(self):
        workspace = self.center()
        workspace.game.set(workspace._game_labels["origins"])
        worker_started = threading.Event()
        release_worker = threading.Event()
        self.addCleanup(release_worker.set)

        def stalled_read_only_scan(*_args, **_kwargs):
            worker_started.set()
            release_worker.wait(timeout=10)
            return sample_report()

        with patch(
            "koei_editor.shared.game_troubleshooting_gui.diagnose_game",
            side_effect=stalled_read_only_scan,
        ):
            workspace.scan()
            self.assertTrue(worker_started.wait(timeout=2), "Scan worker did not start.")
            self.assertTrue(workspace.busy)
            self.assertTrue(workspace.shutdown_safe_while_busy)

            shutdown_state = []
            original_destroy = self.root.destroy

            def verify_close_before_destroy():
                shutdown_state.append((workspace._closed, workspace._poll_id))
                original_destroy()

            self.root.destroy = verify_close_before_destroy
            self.app.close()
            self.root.destroy = original_destroy

        self.assertEqual(shutdown_state, [(True, None)])

    def test_application_close_still_blocks_for_unrelated_copied_save_work(self):
        class BusyCopiedSaveWorkspace:
            busy = True
            shutdown_safe_while_busy = True

            def close(self):
                raise AssertionError("Application close must wait for copied-save work.")

        self.app.save_library = BusyCopiedSaveWorkspace()
        with (
            patch("tkinter.messagebox.showinfo") as show_info,
            patch.object(self.root, "destroy") as destroy,
        ):
            self.app.close()

        show_info.assert_called_once()
        self.assertIs(show_info.call_args.kwargs.get("parent"), self.root)
        destroy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
