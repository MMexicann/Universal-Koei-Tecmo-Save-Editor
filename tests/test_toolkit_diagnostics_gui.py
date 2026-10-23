"""Lazy diagnostic navigation preserves editor state and exports only on request."""
import copy
import json
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.shared.appearance import THEMES
from koei_editor.shared.help_center import HelpCenter


class DiagnosticsGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.geometry('680x600')
        self.center = HelpCenter(self.root, self.root)
        self.center.frame.pack(fill='both', expand=True)
        self.root.update()

    def tearDown(self):
        if hasattr(self, 'root'):
            try:
                self.root.destroy()
            except tk.TclError:
                pass

    def test_lazy_panel_refresh_language_theme_and_small_layout(self):
        self.assertNotIn('diagnostics', self.center._panels)
        self.center.show_tab('diagnostics')
        self.root.update()
        panel = self.center._panels['diagnostics']
        original = panel.report
        self.assertEqual(json.loads(panel.preview.get('1.0', 'end')), original)
        self.center.apply_theme(THEMES['Dark'])
        self.center.set_text_size(14, 'Helvetica')
        self.center.set_language('de')
        self.root.geometry('520x480')
        self.root.update()
        self.assertIs(panel.report, original)
        self.assertEqual(panel.title.cget('text'), 'Toolkit-Diagnose')
        self.assertEqual(str(panel.preview.cget('state')), 'disabled')
        self.assertEqual(panel._button_columns, 1)
        for button in (panel.refresh_button, panel.copy_button, panel.export_button):
            self.assertLessEqual(button.winfo_x() + button.winfo_width(), panel.actions.winfo_width())
            self.assertTrue(button.winfo_viewable())
        panel.refresh_button.invoke()
        self.assertEqual(panel.report['schema'], 'koei-toolkit-diagnostics')
        self.center.show_tab('help')
        self.center.show_tab('diagnostics')
        self.assertIs(self.center._panels['diagnostics'], panel)

    def test_copy_is_explicit_export_cancel_and_no_overwrite(self):
        with patch.object(self.root, 'clipboard_clear') as clear:
            self.center.show_tab('diagnostics')
            self.root.update()
            panel = self.center._panels['diagnostics']
            panel.refresh()
            clear.assert_not_called()
        with patch.object(self.root, 'clipboard_clear') as clear, \
                patch.object(self.root, 'clipboard_append') as append:
            panel.copy_button.invoke()
        clear.assert_called_once_with()
        self.assertEqual(json.loads(append.call_args.args[0]), panel.report)
        with patch('koei_editor.shared.diagnostics_gui.filedialog.asksaveasfilename', return_value=''), \
                patch('koei_editor.shared.diagnostics_gui.export_report') as export:
            panel.export_button.invoke()
        export.assert_not_called()
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'support.json'
            with patch('koei_editor.shared.diagnostics_gui.filedialog.asksaveasfilename', return_value=str(destination)):
                panel.export_button.invoke()
                original = destination.read_bytes()
                with patch('koei_editor.shared.diagnostics_gui.messagebox.showerror') as error:
                    panel.export_button.invoke()
                error.assert_called_once()
            self.assertEqual(json.loads(original), panel.report)
            self.assertEqual(destination.read_bytes(), original)

    def test_destroying_only_panel_during_file_dialog_never_writes(self):
        self.center.show_tab('diagnostics')
        panel = self.center._panels['diagnostics']
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'must-not-write.json'
            def close_panel(**_kwargs):
                panel.frame.destroy()
                return str(destination)
            with patch('koei_editor.shared.diagnostics_gui.filedialog.asksaveasfilename', side_effect=close_panel), \
                    patch('koei_editor.shared.diagnostics_gui.messagebox.showerror') as error:
                panel.export()
                panel.copy_report()
                panel.refresh()
            self.assertFalse(destination.exists())
            error.assert_not_called()

    def test_destroying_root_during_file_dialog_never_writes(self):
        self.center.show_tab('diagnostics')
        panel = self.center._panels['diagnostics']
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'must-not-write.json'
            def close_root(**_kwargs):
                self.root.destroy()
                return str(destination)
            with patch('koei_editor.shared.diagnostics_gui.filedialog.asksaveasfilename', side_effect=close_root), \
                    patch('koei_editor.shared.diagnostics_gui.messagebox.showerror') as error:
                panel.export()
                panel.copy_report()
                panel.refresh()
            self.assertFalse(destination.exists())
            error.assert_not_called()

    def test_native_dialog_error_after_root_destruction_does_not_escape_or_write(self):
        self.center.show_tab('diagnostics')
        panel = self.center._panels['diagnostics']
        def native_close(**_kwargs):
            self.root.destroy()
            raise tk.TclError('PRIVATE_NATIVE_DIALOG_SENTINEL')
        with patch('koei_editor.shared.diagnostics_gui.filedialog.asksaveasfilename', side_effect=native_close), \
                patch('koei_editor.shared.diagnostics_gui.export_report') as export, \
                patch('koei_editor.shared.diagnostics_gui.messagebox.showerror') as error:
            panel.export()
        export.assert_not_called()
        error.assert_not_called()

    def test_native_dialog_failure_with_live_panel_has_static_error(self):
        self.center.show_tab('diagnostics')
        panel = self.center._panels['diagnostics']
        with patch('koei_editor.shared.diagnostics_gui.filedialog.asksaveasfilename', side_effect=tk.TclError('PRIVATE_NATIVE_DIALOG_SENTINEL')), \
                patch('koei_editor.shared.diagnostics_gui.export_report') as export, \
                patch('koei_editor.shared.diagnostics_gui.messagebox.showerror') as error:
            panel.export()
        export.assert_not_called()
        error.assert_called_once()
        self.assertNotIn('PRIVATE_NATIVE_DIALOG_SENTINEL', str(error.call_args))

    def test_reentrant_refresh_does_not_change_reviewed_export_snapshot(self):
        self.center.show_tab('diagnostics')
        panel = self.center._panels['diagnostics']
        reviewed = copy.deepcopy(panel.report)
        updated = copy.deepcopy(reviewed)
        updated['application']['version'] = '9.0'
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'reviewed.json'
            def refresh_from_dialog(**_kwargs):
                with patch('koei_editor.shared.diagnostics_gui.collect_diagnostics', return_value=updated):
                    panel.refresh()
                return str(destination)
            with patch('koei_editor.shared.diagnostics_gui.filedialog.asksaveasfilename', side_effect=refresh_from_dialog):
                panel.export()
            self.assertEqual(json.loads(destination.read_text()), reviewed)
            self.assertEqual(panel.report, updated)
            self.assertEqual(json.loads(panel.preview.get('1.0', 'end')), updated)

    def test_uncertain_publication_is_reported_without_retry_or_path_disclosure(self):
        from koei_editor.shared.copy_storage import ChildPublishedUncertainError
        self.center.show_tab('diagnostics')
        panel = self.center._panels['diagnostics']
        destination = 'PRIVATE_REPORT_FILENAME_SENTINEL.json'
        with patch('koei_editor.shared.diagnostics_gui.filedialog.asksaveasfilename', return_value=destination), \
                patch('koei_editor.shared.diagnostics_gui.export_report', side_effect=ChildPublishedUncertainError(destination)) as export, \
                patch('koei_editor.shared.diagnostics_gui.messagebox.showerror') as error:
            panel.export_button.invoke()
        self.assertEqual(export.call_count, 1)
        self.assertNotIn(destination, str(error.call_args))
        self.assertIn('may already exist', panel.status.get())

    def test_application_route_keeps_existing_staged_session(self):
        from koei_editor.application import Application
        from tests.test_origins_parser import fixture
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'copy.dat'
            raw = fixture()
            source.write_bytes(raw)
            window = tk.Toplevel(self.root)
            try:
                app = Application(window, preferences_path=Path(folder) / 'theme.json', persist_preferences=False)
                editor = app.select_game('origins')
                self.assertTrue(editor.open_path(source))
                editor.stage_values({'gold': 4321})
                pending, history = dict(editor.changes), list(editor.history)
                app.execute_command('tool:diagnostics')
                self.root.update()
                self.assertEqual(app.help_center.selected_tab(), 'diagnostics')
                self.assertIn('diagnostics', app.help_center._panels)
                self.assertIn('tool:diagnostics', app.shell_settings.recent)
                app.select_game('origins')
                self.assertIs(app.sessions['origins'][1], editor)
                self.assertEqual((editor.changes, editor.history), (pending, history))
                self.assertEqual(source.read_bytes(), raw)
            finally:
                window.destroy()


if __name__ == '__main__':
    unittest.main()
