"""Actual Tk comparison, retained sessions, worker revisions and paged records."""
from dataclasses import replace
from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.application import Application
from koei_editor.shared import save_comparison as backend
from koei_editor.shared.comparison_gui import ComparisonWorkspace
from koei_editor.games.deception4_ps3 import parser
from tests.test_ps3_new_families import fixture
from tests.test_ps3_expansion import PS3ContextTests


class ComparisonGuiTests(unittest.TestCase):
    def setUp(self):
        try:self.root=tk.Tk()
        except tk.TclError as error:self.skipTest(str(error))
        self.addCleanup(self.root.destroy);self.root.withdraw()
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.folder=Path(temporary.name)
        self.first=self.folder/'first.bin';self.first.write_bytes(fixture(parser))
        self.second=self.folder/'second.bin';self.second.write_bytes(parser.serialize(parser.decode(fixture(parser)),{'warl':32}))
        (self.folder/'PARAM.SFO').write_bytes(PS3ContextTests.metadata('NPUB31442-GAMEDATA-10'))

    def workspace(self):
        workspace=ComparisonWorkspace(self.root,self.root)
        label=next(label for label,game in workspace._games.items() if game==parser.GAME_ID)
        workspace.game.set(label);workspace.first.set(str(self.first));workspace.second.set(str(self.second))
        return workspace

    def finish(self,workspace):
        deadline=time.monotonic()+10
        while workspace.busy and time.monotonic()<deadline:
            self.root.update();time.sleep(0.01)
        self.assertFalse(workspace.busy,'Comparison worker did not finish')

    def test_real_copy_worker_search_report_and_source_preservation(self):
        workspace=self.workspace();workspace.compare();self.finish(workspace)
        self.assertEqual(len(workspace.table.get_children()),1)
        values=workspace.table.item(workspace.table.get_children()[0],'values')
        self.assertEqual(values[1:4],('Warl','137','32'))
        workspace.search.set('missing');self.assertFalse(workspace.table.get_children())
        workspace.search.set('warl');self.assertEqual(len(workspace.table.get_children()),1)
        workspace.filter.set('Available in second');self.assertFalse(workspace.table.get_children())
        workspace.filter.set('All differences');destination=self.folder/'report.json'
        with patch('koei_editor.shared.comparison_gui.filedialog.asksaveasfilename',return_value=str(destination)):
            workspace.export();self.finish(workspace)
        self.assertTrue(destination.exists());self.assertEqual(self.first.read_bytes(),fixture(parser))
        self.assertFalse((self.folder/'UniversalEditorBackups').exists())

    def test_pagination_search_and_availability_filters_cover_all_large_result_rows(self):
        workspace=self.workspace();result=backend.prepare(parser.GAME_ID,self.first,self.second)
        row=result.rows[0]
        rows=tuple(replace(row,id='field_'+str(i),record='Pilot '+str(i),
                          status='available_in_second' if i==749 else 'value_changed') for i in range(750))
        workspace.prepared=replace(result,rows=rows);workspace.refresh()
        self.assertEqual(len(workspace.table.get_children()),250)
        workspace.change_page(1);self.assertEqual(workspace.table.get_children()[0],'250')
        workspace.change_page(1);self.assertEqual(workspace.table.get_children()[-1],'749')
        self.assertEqual(str(workspace.next['state']),'disabled')
        workspace.search.set('Pilot 749');self.assertEqual(workspace.table.get_children(),('749',))
        workspace.search.set('');workspace.filter.set('Available in second')
        self.assertEqual(workspace.table.get_children(),('749',));self.assertEqual(workspace.page,0)
        workspace.filter.set('All differences');self.assertEqual(len(workspace.table.get_children()),250)

    def test_changed_selection_discards_a_late_worker_result(self):
        workspace=self.workspace();entered,release=threading.Event(),threading.Event()
        prepared=backend.prepare(parser.GAME_ID,self.first,self.second)
        def delayed(*_args):entered.set();release.wait(5);return prepared
        with patch('koei_editor.shared.comparison_gui.backend.prepare',side_effect=delayed):
            workspace.compare();self.assertTrue(entered.wait(2))
            workspace.second.set(str(self.first));release.set();self.finish(workspace)
        self.assertIsNone(workspace.prepared);self.assertFalse(workspace.table.get_children())
        self.assertEqual(str(workspace.export_button['state']),'disabled')
        self.assertIn('Selections changed',workspace.status.get())

    def test_failed_open_and_stale_export_leave_workspace_without_reviewable_data(self):
        workspace=self.workspace();errors=[]
        with patch('koei_editor.shared.comparison_gui.messagebox.showerror',side_effect=lambda *a,**k:errors.append(a)):
            workspace.compare();self.finish(workspace)
            self.first.write_bytes(b'changed');output=self.folder/'stale.json'
            with patch('koei_editor.shared.comparison_gui.filedialog.asksaveasfilename',return_value=str(output)):
                workspace.export();self.finish(workspace)
            self.assertFalse(output.exists());self.assertIsNone(workspace.prepared)
            self.assertTrue(errors)
            workspace.compare();self.finish(workspace);self.assertIsNone(workspace.prepared)

    def test_application_retains_comparison_editor_and_converter_and_keeps_ctrl_f_local(self):
        app=Application(self.root,persist_preferences=False)
        editor=app.select_game(parser.GAME_ID)
        app.show_comparison();workspace=app.comparison
        label=next(label for label,game in workspace._games.items() if game==parser.GAME_ID)
        workspace.game.set(label);workspace.first.set(str(self.first));workspace.second.set(str(self.second))
        workspace.compare();self.finish(workspace)
        app.platform_choice.set('PlayStation 3');app.library_search.set('Deception')
        before=(app.platform_choice.get(),app.library_search.get())
        app.focus_library_search();self.assertEqual(before,(app.platform_choice.get(),app.library_search.get()))
        app.show_converter();self.assertFalse(workspace.frame.winfo_manager())
        app.show_library();app.show_comparison();self.assertIs(app.comparison,workspace)
        self.assertEqual(len(workspace.table.get_children()),1)
        self.assertIs(app.select_game(parser.GAME_ID),editor);self.assertFalse(workspace.frame.winfo_manager())
        app.show_comparison();app.apply_theme('Dark');app.apply_theme('Light')
        self.assertIsNone(app.active_game)
        workspace.busy=True
        with patch('koei_editor.application.tk.Misc.destroy') as destroy, \
                patch('tkinter.messagebox.showinfo') as info:
            app.close();self.assertTrue(info.called);destroy.assert_not_called()
        workspace.busy=False
