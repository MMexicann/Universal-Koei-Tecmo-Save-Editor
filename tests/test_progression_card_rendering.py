"""Dashboard navigation keeps selected records and compact tools reachable."""
import tkinter as tk
import unittest
from unittest.mock import Mock

from koei_editor.shared.progression_view import PAGE_SIZE, ProgressionView
from tests.test_progression_view_gui import dashboard


class ProgressionCardRenderingTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.root.destroy)
        self.root.geometry('1180x820')
        self.snapshot = dashboard()
        self.navigate = Mock()
        self.view = ProgressionView(self.root, self.snapshot, on_navigate=self.navigate)
        self.view.pack(fill='both', expand=True)
        self.root.update()

    def test_keyboard_navigation_reveals_selected_record_in_large_grid(self):
        self.view._move_selection(PAGE_SIZE - 1)
        self.root.update()
        self.assertEqual(self.view._selected_id, f'character:{PAGE_SIZE - 1}')
        self.assertGreater(self.view.canvas.yview()[0], 0)
        _, top, _, bottom = self.view.canvas.bbox('card:' + self.view._selected_id)
        viewport_top = self.view.canvas.canvasy(0)
        viewport_bottom = viewport_top + self.view.canvas.winfo_height()
        self.assertLess(top, viewport_bottom)
        self.assertGreater(bottom, viewport_top)
        self.view._move_selection(1)
        self.root.update()
        self.assertEqual(self.view.page_text.get(), 'Page 2 of 3')
        self.assertLessEqual(len(self.view.card_selector['values']), PAGE_SIZE)
        self.navigate.assert_not_called()
        self.assertEqual(self.snapshot, dashboard())

    def test_short_viewport_reveals_filters_and_report_without_losing_selection(self):
        self.root.geometry('800x400')
        self.root.update()
        self.assertTrue(self.view.filter_button.winfo_ismapped())
        self.assertFalse(self.view.filterbar.winfo_ismapped())
        self.view.filter_button.invoke()
        self.root.update()
        self.assertTrue(self.view.filterbar.winfo_ismapped())
        self.assertTrue(self.view.report_button.winfo_ismapped())
        self.view.filter_button.invoke()
        self.root.update()
        self.assertFalse(self.view.filterbar.winfo_ismapped())
        self.assertTrue(self.view.canvas.winfo_ismapped())
        self.assertGreater(self.view.canvas.winfo_height(), 100)
        self.assertEqual(self.view._selected_id, 'character:0')
        self.navigate.assert_not_called()
        self.assertEqual(self.snapshot, dashboard())
