"""Explicit reviewed manager export through the real Workshop widgets."""
import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from koei_editor.shared.mod_workshop.gui import ModWorkshopWindow
from koei_editor.shared.mod_workshop.project_manager import load_project
from tests.test_mod_workshop_manager import make_workshop


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'A graphical display is required.')
class WorkshopManagerGuiTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name).resolve()
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.destroy)
        self.callback = Mock()
        self.workshop = ModWorkshopWindow(self.root, on_manager_package=self.callback)
        self.project, _ = make_workshop(self.folder)
        self.workshop._activate_project(self.project, load_project(self.project))
        self.output = self.folder / 'manager.zip'

    def destroy(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_confirmed_export_invokes_manager_callback_only_after_publication(self):
        def exported(path):
            self.assertEqual(Path(path), self.output)
            self.assertTrue(self.output.is_file())
        self.callback.side_effect = exported
        with patch('koei_editor.shared.mod_workshop.gui.messagebox.askyesno', return_value=True), \
                patch('koei_editor.shared.mod_workshop.gui.filedialog.asksaveasfilename', return_value=str(self.output)), \
                patch('koei_editor.shared.mod_workshop.gui.messagebox.showerror') as error:
            self.workshop.export_for_manager()
        error.assert_not_called()
        self.callback.assert_called_once_with(str(self.output))
        self.assertEqual(self.workshop.last_package_report['status'], 'exported')

    def test_declined_review_does_not_open_destination_dialog_or_call_manager(self):
        with patch('koei_editor.shared.mod_workshop.gui.messagebox.askyesno', return_value=False), \
                patch('koei_editor.shared.mod_workshop.gui.filedialog.asksaveasfilename') as destination:
            self.workshop.export_for_manager()
        destination.assert_not_called()
        self.callback.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_destroying_window_during_destination_dialog_never_exports(self):
        def close(**kwargs):
            self.workshop.window.destroy()
            return str(self.output)
        with patch('koei_editor.shared.mod_workshop.gui.messagebox.askyesno', return_value=True), \
                patch('koei_editor.shared.mod_workshop.gui.filedialog.asksaveasfilename', side_effect=close):
            self.workshop.export_for_manager()
        self.callback.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_uncertain_publication_never_calls_manager_or_claims_export_failed(self):
        from koei_editor.shared.copy_storage import ChildPublishedUncertainError
        with patch('koei_editor.shared.mod_workshop.gui.messagebox.askyesno', return_value=True), \
                patch('koei_editor.shared.mod_workshop.gui.filedialog.asksaveasfilename', return_value=str(self.output)), \
                patch('koei_editor.shared.mod_workshop.manager_export.export_manager_package',
                      side_effect=ChildPublishedUncertainError(self.output)) as export, \
                patch('koei_editor.shared.mod_workshop.gui.messagebox.showerror') as error:
            self.workshop.export_for_manager()
        self.assertEqual(export.call_count, 1)
        self.callback.assert_not_called()
        self.assertIsNone(self.workshop.last_package_report)
        self.assertIn('status uncertain', error.call_args.args[0])
        self.assertNotIn(str(self.output), str(error.call_args))


if __name__ == '__main__':
    unittest.main()
