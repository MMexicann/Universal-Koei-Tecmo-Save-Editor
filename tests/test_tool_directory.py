"""Tools navigation exposes scope and routes without touching save sessions."""
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.application import Application
from koei_editor.shared.tool_directory import ToolEntry, matching_tools


class DirectorySearchTests(unittest.TestCase):
    def test_search_combines_words_and_category_without_changing_entries(self):
        entries = (ToolEntry('tool:manager', 'Mod Manager', 'Mods', 'Nioh 2 PC', 'Local ZIP installation'),
                   ToolEntry('tool:nexus', 'Nexus Mods', 'Mods', 'Website only', 'Registration pending'),
                   ToolEntry('tool:converter', 'Save Converter', 'Saves', 'Qualified routes', 'New copies'))
        self.assertEqual(matching_tools(entries, 'nioh zip', 'Mods'), (entries[0],))
        self.assertEqual(matching_tools(entries, 'nioh', 'Saves'), ())
        self.assertEqual(matching_tools(entries, 'REGISTRATION'), (entries[1],))
        self.assertEqual(matching_tools(entries), entries)


class DirectoryIntegrationTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.destroy_root)
        self.app = Application(self.root, persist_preferences=False)
        self.root.update_idletasks()

    def destroy_root(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_every_directory_action_resolves_and_filtered_open_retains_editor(self):
        editor = self.app.select_game('dw8xl')
        directory = self.app.show_tool_directory()
        actions = {entry.id for entry in self.app.command_entries()}
        self.assertTrue(all(entry.command_id in actions for entry in directory.entries))
        directory.query.set('encyclopedia')
        self.assertEqual(directory.tree.get_children(), ('tool:encyclopedia',))
        directory.tree.selection_set('tool:encyclopedia')
        directory.open_selected()
        self.assertIsNotNone(self.app.encyclopedia)
        self.assertIs(self.app.sessions['dw8xl'][1], editor)
        self.assertFalse(editor.changes)
        self.assertIs(self.app.show_tool_directory(), directory)

    def test_bundled_browser_routes_do_not_open_an_editor(self):
        with patch('koei_editor.shared.browser_companions.BrowserCompanionManager') as manager:
            self.app.execute_command('tool:localization_studio')
            self.app.execute_command('tool:mod_sandbox')
        self.assertEqual([call.args[0] for call in manager.return_value.open.call_args_list],
                         ['localization_studio', 'mod_testing_sandbox'])
        self.assertFalse(self.app.sessions)
        manager.return_value.close()

    def test_nexus_selection_distinguishes_website_from_installation_and_import_is_explicit(self):
        notice = self.app.show_nexus_mods()
        with patch.object(self.app, '_import_nexus_zip') as receive:
            notice.on_local_import = receive
            notice.game_var.set('NIOH 2')
            notice.refresh_capability()
            self.assertEqual(str(notice.import_button['state']), 'normal')
            receive.assert_not_called()
            notice.import_button.invoke()
            receive.assert_called_once_with('nioh2_pc')
            notice.game_var.set('ONE PIECE: PIRATE WARRIORS 4')
            notice.refresh_capability()
            self.assertEqual(str(notice.import_button['state']), 'disabled')
            self.assertIn('no installation adapter', notice.capability.get())

    def test_shutdown_closes_browser_listener(self):
        from unittest.mock import Mock
        manager = self.app.browser_companions = Mock()
        self.app.close()
        manager.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
