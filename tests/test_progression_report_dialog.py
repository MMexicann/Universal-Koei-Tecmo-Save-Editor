"""Report selection stays read only and excludes sections before exporting."""
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from koei_editor.shared.progression_report import show_report_dialog
from koei_editor.shared.appearance import THEMES
from tests.test_progression_report_security import ParsedReport, report_snapshot


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


class ProgressionReportDialogTests(unittest.TestCase):
    def test_real_dialog_section_selection_export_and_cancellation(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(root.destroy)
        root.geometry('800x700')
        snapshot = report_snapshot()
        window = show_report_dialog(root, snapshot, theme='Dark')
        root.update()
        lists = [w for w in descendants(window) if isinstance(w, tk.Listbox)]
        sections, records = lists
        self.assertEqual(str(sections.cget('background')), THEMES['Dark']['surface'])
        self.assertEqual(str(records.cget('foreground')), THEMES['Dark']['text'])
        self.assertEqual(sections.curselection(), (0, 1))
        self.assertEqual(records.size(), 3)
        # Selecting sections removes excluded records before the writer sees them.
        sections.selection_clear(0, 'end')
        sections.selection_set(0)
        sections.event_generate('<<ListboxSelect>>')
        root.update()
        self.assertEqual(records.size(), 2)
        records.selection_set(0)
        records.event_generate('<<ListboxSelect>>')
        controls = list(descendants(window))
        save = next(w for w in controls if isinstance(w, ttk.Button) and w.cget('text') == 'Save HTML report…')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'selected.html'
            with patch('tkinter.filedialog.asksaveasfilename', return_value=str(path)), \
                    patch('tkinter.messagebox.showinfo') as info, \
                    patch('tkinter.messagebox.showerror') as error:
                save.invoke()
            error.assert_not_called()
            info.assert_called_once()
            data = ParsedReport(path.read_text(encoding='utf-8')).data
            self.assertEqual([s['id'] for s in data['sections']], ['shown'])
            self.assertEqual(data['comparisons'], ['first'])
            self.assertEqual(data['theme'], 'Dark')
            self.assertFalse(window.winfo_exists())
        self.assertEqual(snapshot, report_snapshot())
        cancel_window = show_report_dialog(root, snapshot)
        cancel = next(w for w in descendants(cancel_window)
                      if isinstance(w, ttk.Button) and w.cget('text') == 'Cancel')
        cancel.invoke()
        self.assertFalse(cancel_window.winfo_exists())


if __name__ == '__main__':
    unittest.main()
