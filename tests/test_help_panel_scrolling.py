"""Long global forms remain reachable at minimum size and enlarged text."""
import tkinter as tk
from tkinter import ttk
import unittest

from koei_editor.application import Application


class HelpPanelScrollingTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.root.destroy)
        self.app = Application(self.root, persist_preferences=False)
        self.root.geometry('780x680')
        self.app.text_size_choice.set('140%')
        self.app.change_text_size()
        self.root.update()

    def buttons(self, frame):
        pending, found = [frame], []
        while pending:
            widget = pending.pop()
            pending.extend(widget.winfo_children())
            if isinstance(widget, (ttk.Button, ttk.Checkbutton)):
                found.append(widget)
        return found

    def assert_revealed(self, widget, mount):
        widget.focus_force()
        self.root.update()
        self.assertTrue(widget.winfo_ismapped())
        self.assertGreaterEqual(widget.winfo_rooty(), mount.canvas.winfo_rooty())
        self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                             mount.canvas.winfo_rooty() + mount.canvas.winfo_height())

    def test_minimum_size_enlarged_text_can_focus_every_action_in_both_languages(self):
        for language in ('English', 'Deutsch'):
            self.app.language_choice.set(language)
            self.app.change_language()
            for tab in ('validation', 'feedback', 'plugins'):
                self.app.show_help(tab)
                self.root.update()
                center = self.app.help_center
                panel, mount = center._panels[tab], center._panel_mounts[tab]
                actions = self.buttons(panel.frame)
                self.assertTrue(actions)
                for widget in actions:
                    with self.subTest(language=language, tab=tab, action=widget.cget('text')):
                        self.assert_revealed(widget, mount)

    def test_wheel_and_page_navigation_are_scoped_and_keep_nested_text_scroll(self):
        self.app.show_help('validation')
        self.root.update()
        center = self.app.help_center
        panel, mount = center._panels['validation'], center._panel_mounts['validation']
        control = self.buttons(panel.frame)[0]
        mount.canvas.yview_moveto(0)
        control.event_generate('<MouseWheel>', delta=-120)
        self.root.update()
        self.assertGreater(mount.canvas.yview()[0], 0)
        mount.canvas.yview_moveto(0)
        panel.preview.event_generate('<MouseWheel>', delta=-120)
        self.assertEqual(mount.canvas.yview()[0], 0)
        self.app.home_button.event_generate('<MouseWheel>', delta=-120)
        self.assertEqual(mount.canvas.yview()[0], 0)
        self.assert_revealed(control, mount)
        control.event_generate('<Control-Home>')
        self.assertEqual(mount.canvas.yview()[0], 0)
        control.event_generate('<Next>')
        self.assertGreater(mount.canvas.yview()[0], 0)

    def test_locale_and_theme_preserve_workflow_and_refresh_descendant_focus_bindings(self):
        self.app.show_help('validation')
        self.root.update()
        center = self.app.help_center
        panel, mount = center._panels['validation'], center._panel_mounts['validation']
        record = panel.record.record_step('prepare_copy', 'passed')
        panel.record = record
        self.app.language_choice.set('Deutsch')
        self.app.change_language()
        self.app.apply_theme('Dark')
        self.root.update()
        self.assertIs(center._panels['validation'], panel)
        self.assertIs(center._panel_mounts['validation'], mount)
        self.assertIs(panel.record, record)
        for widget in self.buttons(panel.frame):
            self.assert_revealed(widget, mount)
        self.assertEqual(mount.canvas.cget('background'), '#18212d')


if __name__ == '__main__':
    unittest.main()
