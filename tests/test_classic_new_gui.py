"""Copied-save Tk workflows for the two new classic scalar adapters."""
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from tests.test_bandit_kings_mac import procedural_raw as bandit_raw
from tests.test_nobunaga_ambition_nes import procedural_raw as nobunaga_raw


class ClassicCopyAliasTests(unittest.TestCase):
    def test_both_profiles_reject_resolved_copy_aliases(self):
        from koei_editor.games.bandit_kings_mac import parser as bandit
        from koei_editor.games.nobunaga_ambition_nes import parser as nobunaga
        from koei_editor.games.dw3.models import SaveError
        for backend, fixture, suffix in ((bandit, bandit_raw, '.cim'),
                                         (nobunaga, nobunaga_raw, '.sav')):
            with self.subTest(game=backend.GAME_ID), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)
                source = folder / ('copy' + suffix)
                source.write_bytes(fixture())
                document = backend.read_save(source)
                linked = folder / ('alias' + suffix)
                os.link(source, linked)
                with self.assertRaises(SaveError):
                    backend.read_save(linked)
                with self.assertRaises(SaveError):
                    backend.save_as(document, {}, folder / ('edited' + suffix))
                linked.unlink()
                try:
                    linked.symlink_to(source)
                except OSError:
                    continue
                with self.assertRaises(SaveError):
                    backend.read_save(linked)
                directory = folder / 'directory-alias'
                directory.symlink_to(folder, target_is_directory=True)
                with self.assertRaises(SaveError):
                    backend.save_as(document, {}, directory / ('edited' + suffix))
                backup = backend.backup(document)
                with self.assertRaises(SaveError):
                    backend.restore(backup, directory / ('restored' + suffix))


class ClassicNewGuiTests(unittest.TestCase):
    def test_both_editors_open_stage_undo_review_theme_save_and_restore(self):
        import tkinter as tk
        from koei_editor.games.bandit_kings_mac.editor import Editor as BanditEditor
        from koei_editor.games.nobunaga_ambition_nes.editor import Editor as NobunagaEditor
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        root.withdraw()
        try:
            for editor_type, fixture, extension in ((BanditEditor, bandit_raw, '.cim'),
                                                    (NobunagaEditor, nobunaga_raw, '.sav')):
                with self.subTest(game=editor_type.game_id), tempfile.TemporaryDirectory() as temporary:
                    for child in root.winfo_children():
                        child.destroy()
                    folder = Path(temporary)
                    source, target = folder / ('copy' + extension), folder / ('edited' + extension)
                    source.write_bytes(fixture())
                    editor = editor_type(root)
                    with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)), \
                         patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                        editor.open(); errors.assert_not_called()
                    self.assertTrue(editor.presentation.inspection_tables(editor.document))
                    field = editor.adapter.fields_for(editor.document)[0]
                    editor.fields.selection_set(field.id)
                    editor.value.set('0'); editor.apply_selected()
                    self.assertEqual(editor.changes, {field.id: 0})
                    editor.undo(); self.assertEqual(editor.changes, {})
                    editor.value.set('0'); editor.apply_selected()
                    editor.review()
                    for child in root.winfo_children():
                        if isinstance(child, tk.Toplevel):
                            child.destroy()
                    editor.apply_theme('Dark')
                    expected = editor.adapter.serialize(editor.document, {field.id: 0})
                    with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(target)), \
                         patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                        editor.save_as(); errors.assert_not_called()
                    self.assertEqual(target.read_bytes(), expected)
                    self.assertEqual(source.read_bytes(), fixture())
                    backup = next((folder / 'WarriorsEditorBackups').glob('*' + extension))
                    restored = folder / ('restored' + extension)
                    with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(backup)), \
                         patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(restored)), \
                         patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                        editor.restore(); errors.assert_not_called()
                    self.assertEqual(restored.read_bytes(), fixture())
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
