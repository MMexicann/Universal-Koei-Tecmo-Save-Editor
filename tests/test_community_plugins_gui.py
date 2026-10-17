"""Real Tk plugin discovery, preview, explicit snapshot approval and revocation."""
import json
import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.shared.appearance import THEMES
from koei_editor.shared.plugin_gui import PluginPanel


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'A graphical display is required.')
class CommunityPluginGuiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.root = tk.Tk()
        self.root.geometry('900x720')
        self.addCleanup(self.root.destroy)
        self.notifications = []
        self.panel = PluginPanel(self.root, self.root, on_change=self.notifications.append)
        self.panel.frame.pack(fill='both', expand=True)
        template = Path(__file__).resolve().parents[1] / 'tools' / 'community_plugin_template' / 'example.plugin.json'
        self.path = self.folder / 'example.plugin.json'
        self.path.write_bytes(template.read_bytes())
        self.root.update()

    def load(self):
        self.assertTrue(self.panel.load_directory(self.folder))
        self.root.update()

    def approve(self):
        self.panel.review_check.invoke()
        self.panel.enable_button.invoke()
        self.root.update()

    def test_inspection_previews_digest_capabilities_and_all_content_but_never_auto_enables(self):
        self.load()
        content = self.panel.preview.get('1.0', 'end')
        candidate = self.panel.catalog.entries[0].candidate
        self.assertIn(candidate.sha256, content)
        self.assertIn('commands, help, workflows', content)
        self.assertIn('Originalkopien aufbewahren', content)
        self.assertEqual(self.panel.catalog.contributions(), ())
        self.assertEqual(str(self.panel.enable_button['state']), 'disabled')
        self.panel.enable_selected()
        self.assertEqual(self.panel.catalog.contributions(), ())

    def test_review_checkbox_enables_exact_snapshot_and_disable_revokes_content(self):
        self.load()
        self.approve()
        self.assertEqual(len(self.panel.catalog.contributions()), 6)
        self.assertTrue(self.panel.catalog.entries[0].enabled)
        self.assertEqual(str(self.panel.disable_button['state']), 'normal')
        self.panel.disable_button.invoke()
        self.root.update()
        self.assertEqual(self.panel.catalog.contributions(), ())
        self.assertEqual(len(self.notifications), 3)

    def test_search_finds_declared_workflow_steps_and_hidden_selection_cannot_enable(self):
        self.load()
        self.panel.search.set('Sicherung')
        self.root.update()
        self.assertEqual(len(self.panel.tree.get_children()), 1)
        self.panel.review_check.invoke()
        self.panel.search.set('does not exist')
        self.root.update()
        self.assertEqual(self.panel.tree.get_children(), ())
        self.assertFalse(self.panel.reviewed.get())
        self.panel.enable_selected()
        self.assertEqual(self.panel.catalog.contributions(), ())

    def test_reinspection_revokes_session_approval_and_changed_snapshot_needs_review(self):
        self.load()
        self.approve()
        old_digest = self.panel.catalog.entries[0].candidate.sha256
        value = json.loads(self.path.read_bytes())
        value['description'] = 'A changed snapshot'
        self.path.write_text(json.dumps(value))
        self.load()
        self.assertEqual(self.panel.catalog.contributions(), ())
        self.assertNotEqual(old_digest, self.panel.catalog.entries[0].candidate.sha256)
        self.assertFalse(self.panel.reviewed.get())

    def test_rejected_manifest_cannot_be_approved_and_errors_are_safe(self):
        self.path.write_text('{"module":"os.system"}')
        self.load()
        self.assertTrue(self.panel.catalog.entries[0].error)
        self.assertEqual(str(self.panel.review_check['state']), 'disabled')
        self.assertEqual(str(self.panel.enable_button['state']), 'disabled')
        with patch('koei_editor.shared.plugin_gui.messagebox.showerror') as error:
            self.assertFalse(self.panel.load_directory(self.folder / 'missing'))
        self.assertNotIn(str(self.folder), error.call_args.args[1])

    def test_bilingual_labels_theme_and_keyboard_access_to_preview(self):
        self.load()
        self.panel.set_language('de')
        self.root.update()
        self.assertEqual(self.panel.title_label['text'], 'Community-Plugins')
        self.assertIn('prüfen', self.panel.browse_button['text'])
        self.assertIn('Berechtigungen', self.panel.preview.get('1.0', 'end'))
        self.panel.apply_theme(THEMES['Dark'])
        self.assertEqual(self.panel.preview['background'], THEMES['Dark']['surface'])
        self.assertEqual(str(self.panel.preview['takefocus']), '1')
        self.panel.search_entry.focus_force()
        self.root.update()
        self.assertIs(self.root.focus_get(), self.panel.search_entry)
        self.panel.search.set('test')
        self.panel.search_entry.event_generate('<Escape>')
        self.root.update()
        self.assertEqual(self.panel.search.get(), '')


if __name__ == '__main__':
    unittest.main()
