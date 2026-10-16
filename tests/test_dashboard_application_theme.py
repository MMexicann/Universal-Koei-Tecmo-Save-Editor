"""Application appearance reaches graphics in every retained editor session."""
import os
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import Mock

from koei_editor.application import Application, _smoke_progression_views
from koei_editor.shared.appearance import THEMES


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'),
                     'A graphical display is required.')
class DashboardApplicationThemeTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.app = Application(self.root, persist_preferences=False)

    def test_graphics_in_all_retained_sessions_repaint_without_editing_or_recursion(self):
        editors = []
        for index in range(2):
            frame = ttk.Frame(self.app.workspace)
            canvas = tk.Canvas(frame)
            item = canvas.create_text(30, 30, text='Opened level: 7', fill='#000000')
            pending, history = {'mapped-field': 8}, [{}]
            editor = SimpleNamespace(theme_name=tk.StringVar(self.root, value='Light'),
                                     changes=pending, history=history,
                                     apply_theme=Mock(side_effect=AssertionError('Recursive theme callback')))

            def paint(name, *, editor=editor, canvas=canvas, item=item):
                self.assertEqual(editor.theme_name.get(), name)
                canvas.itemconfigure(item, fill=THEMES[name]['text'])

            editor.theme_dashboard = Mock(side_effect=paint)
            self.app.sessions[f'retained-{index}'] = (frame, editor)
            editors.append((editor, canvas, item, pending, history))
        # An optional dashboard hook must not become a new session requirement.
        self.app.sessions['without-dashboard'] = (
            ttk.Frame(self.app.workspace), SimpleNamespace(theme_name=tk.StringVar(self.root)))
        for name in ('Dark', 'Light'):
            self.app.apply_theme(name)
            for editor, canvas, item, pending, history in editors:
                self.assertEqual(canvas.itemcget(item, 'fill'), THEMES[name]['text'])
                self.assertEqual(canvas.itemcget(item, 'text'), 'Opened level: 7')
                self.assertIs(editor.changes, pending)
                self.assertEqual(editor.changes, {'mapped-field': 8})
                self.assertIs(editor.history, history)
                self.assertEqual(editor.history, [{}])
                editor.theme_dashboard.assert_called_with(name)
                editor.apply_theme.assert_not_called()
        self.assertEqual(self.app.sessions['without-dashboard'][1].theme_name.get(), 'Light')

    def test_packaged_smoke_draws_samples_and_restores_the_original_empty_dashboards(self):
        editors = [self.app.select_game(game_id) for game_id in ('origins', 'dw3')]
        snapshots = [editor.dashboard_view.dashboard for editor in editors]
        self.assertEqual(_smoke_progression_views(self.app), 2)
        for editor, snapshot in zip(editors, snapshots):
            self.assertIs(editor.dashboard_view.dashboard, snapshot)
            self.assertIsNone(editor.document)
            self.assertFalse(editor.changes)
            self.assertFalse(editor.history)
            self.assertEqual(editor.dashboard_view.palette, THEMES['Light'])
            self.assertFalse(editor.dashboard_view.dashboard.sections)


if __name__ == '__main__':
    unittest.main()
