"""Real Tk worker integration for private vault imports, history and restore."""
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from koei_editor.shared.appearance import THEMES
from koei_editor.shared.save_vault_gui import SaveVaultWorkspace
from tests.test_verified_editors import synthetic_raw


class SaveVaultGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.root.destroy)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name).resolve()
        self.path = self.folder / 'source.dat'
        self.path.write_bytes(synthetic_raw('dw8xl'))
        self.on_open = Mock()
        self.workspace = SaveVaultWorkspace(self.root, self.root, self.on_open,
                                           vault_root=self.folder / 'vault')
        self.workspace.frame.pack(fill='both', expand=True)
        self.root.geometry('1150x760'); self.root.update()
        label = next(label for label, game_id in self.workspace._games.items() if game_id == 'dw8xl')
        self.workspace.game.set(label)

    def wait(self):
        deadline = time.monotonic() + 30
        while self.workspace.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(.01)
        self.assertFalse(self.workspace.busy, 'Vault worker did not finish.')
        self.root.update()

    def import_copy(self, label, *, parent=False, branch='main'):
        with patch('koei_editor.shared.save_vault_gui.filedialog.askopenfilename', return_value=str(self.path)), \
             patch('koei_editor.shared.save_vault_gui.simpledialog.askstring', side_effect=[label, 'Campaign', branch]), \
             patch('koei_editor.shared.save_vault_gui.messagebox.askyesno', return_value=parent):
            self.workspace.import_copy()
        self.wait()
        self.assertIn('snapshots loaded', self.workspace.status.get())

    def test_opening_workspace_alone_does_not_create_storage_or_capture(self):
        self.assertFalse(self.workspace.vault_root.exists())
        self.assertFalse(self.workspace.has_pending_work())
        self.workspace.focus_search(); self.root.update()
        for theme in THEMES.values():
            self.workspace.apply_theme(theme)
        self.assertFalse(self.workspace.vault_root.exists())
        self.assertTrue(self.workspace.close())

    def test_worker_import_parent_branch_history_verify_compare_and_open_new_copy(self):
        self.import_copy('Chapter one')
        first = self.workspace._rows[0]
        self.workspace.tree.selection_set(first['id'])
        self.import_copy('Challenge branch', parent=True, branch='challenge')
        second = self.workspace._rows[0]
        self.assertEqual(second['parent'], first['id'])
        self.workspace.branch.set('challenge'); self.root.update()
        self.assertEqual(self.workspace.tree.get_children(), (second['id'],))
        self.workspace.search.set('missing'); self.root.update()
        self.assertEqual(self.workspace.tree.get_children(), ())
        self.workspace.search.set(''); self.workspace.branch.set('All branches')
        self.workspace.tree.selection_set(second['id'])
        self.workspace.verify_selected(); self.wait()
        self.assertIn('verified', self.workspace.status.get())
        with patch.object(self.workspace, '_show_rows') as show:
            self.workspace.show_history(); self.wait()
            self.assertEqual(show.call_args.args[0], 'Parent history')
            self.assertEqual([row[0] for row in show.call_args.args[2]], ['Challenge branch', 'Chapter one'])
        self.workspace.tree.selection_set((first['id'], second['id']))
        with patch.object(self.workspace, '_show_rows') as show:
            self.workspace.compare_selected(); self.wait()
            self.assertEqual(show.call_args.args[2], ())
        self.workspace.tree.selection_set(second['id'])
        with patch('koei_editor.shared.save_vault_gui.filedialog.askdirectory', return_value=str(self.folder)), \
             patch('koei_editor.shared.save_vault_gui.simpledialog.askstring', return_value='restored'):
            self.workspace.export_selected(open_after=True)
        self.wait()
        self.on_open.assert_called_once_with('dw8xl', self.folder / 'restored' / 'source.dat')
        self.assertEqual((self.folder / 'restored' / 'source.dat').read_bytes(), self.path.read_bytes())

    def test_collection_creation_is_explicit_and_working_operations_block_close(self):
        with patch('koei_editor.shared.save_vault_gui.simpledialog.askstring', return_value='Challenge runs'):
            self.workspace.create_collection()
        self.assertTrue(self.workspace.has_pending_work())
        self.assertFalse(self.workspace.close())
        self.wait()
        self.assertIn('Challenge runs', self.workspace.collections['values'])
        self.assertTrue(self.workspace.close())

    def test_invalid_profile_import_is_reported_without_personal_path(self):
        self.path.write_bytes(b'not this profile')
        with patch('koei_editor.shared.save_vault_gui.filedialog.askopenfilename', return_value=str(self.path)), \
             patch('koei_editor.shared.save_vault_gui.simpledialog.askstring', side_effect=['Bad copy', 'Campaign', 'main']):
            self.workspace.import_copy()
        self.wait()
        self.assertIn('Operation failed', self.workspace.status.get())
        self.assertNotIn(str(self.folder), self.workspace.status.get())
        self.assertEqual(self.workspace._rows, ())

    def test_large_metadata_result_pages_and_filters_without_unbounded_tree(self):
        self.workspace._rows = tuple({'id': f'{i:032x}', 'label': f'Snapshot {i}', 'game_id': 'dw8xl',
            'collection': 'Campaign', 'branch': 'main', 'created_utc': '2026-10-16T00:00:00Z', 'parent': None}
            for i in range(502))
        self.workspace._render()
        self.assertEqual(len(self.workspace.tree.get_children()), 100)
        self.workspace.change_page(5)
        self.assertEqual(len(self.workspace.tree.get_children()), 2)
        self.workspace.search.set('Snapshot 501')
        self.assertEqual(len(self.workspace.tree.get_children()), 1)
        self.assertEqual(self.workspace._page, 0)

    def test_pinned_comparison_first_snapshot_survives_page_changes(self):
        self.workspace._rows = tuple({'id': f'{i:032x}', 'label': f'Snapshot {i}', 'game_id': 'dw8xl',
            'collection': 'Campaign', 'branch': 'main', 'created_utc': '2026-10-16T00:00:00Z', 'parent': None}
            for i in range(202))
        self.workspace._render()
        self.workspace.tree.selection_set(f'{0:032x}')
        self.workspace.pin_comparison()
        self.workspace.change_page(2)
        self.workspace.tree.selection_set(f'{201:032x}')
        with patch.object(self.workspace, '_run') as run, \
             patch('koei_editor.shared.save_vault_gui.save_vault.Vault') as vault:
            self.workspace.compare_selected()
            operation = run.call_args.args[0]
            operation()
            vault.return_value.compare.assert_called_once_with(f'{0:032x}', f'{201:032x}')


if __name__ == '__main__':
    unittest.main()
