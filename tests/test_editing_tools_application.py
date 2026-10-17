"""Application entries reach retained editing tools through existing save sessions."""
from pathlib import Path
import tempfile
import time
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from koei_editor.application import Application, VERSION
from tests.test_origins_parser import fixture


class EditingToolsApplicationTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.root.destroy)
        area = tempfile.TemporaryDirectory()
        self.addCleanup(area.cleanup)
        self.folder = Path(area.name)
        self.app = Application(self.root, persist_preferences=False,
                               preferences_path=self.folder / 'preferences.json')
        self.root.geometry('1080x820')

    def open_destination(self):
        editor = self.app.select_game('origins')
        path = self.folder / 'SLOT0000.dat'
        path.write_bytes(fixture())
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            self.assertTrue(editor.open_path(path))
            errors.assert_not_called()
        return editor

    def test_native_menu_and_workflow_footer_relabel_without_replacing_commands(self):
        commands = tuple(self.app.editing_tools_menu.entrycget(index, 'command') for index in (0, 1, 3))
        for language, header, labels, workflow in (
                ('English', 'Editing and Research',
                 ('Reusable Editing Presets', 'Transfer from Save Copy', 'Save Research Lab'), 'Workflow Builder'),
                ('Deutsch', 'Bearbeitung und Forschung',
                 ('Wiederverwendbare Bearbeitungsvorlagen', 'Aus Spielstandkopie übertragen',
                  'Spielstand-Forschungslabor'), 'Ablaufeditor'),
                ('English', 'Editing and Research',
                 ('Reusable Editing Presets', 'Transfer from Save Copy', 'Save Research Lab'), 'Workflow Builder')):
            with self.subTest(language=language):
                self.app.language_choice.set(language)
                self.app.change_language()
                self.root.update()
                self.assertEqual(self.app.tools_menu_bar.entrycget('end', 'label'), header)
                self.assertEqual(tuple(self.app.editing_tools_menu.entrycget(index, 'label')
                                       for index in (0, 1, 3)), labels)
                self.assertEqual(self.app.workflow_button.cget('text'), workflow)
                self.assertTrue(self.app.workflow_button.winfo_ismapped())
                self.assertEqual(tuple(self.app.editing_tools_menu.entrycget(index, 'command')
                                       for index in (0, 1, 3)), commands)

    def test_direct_tool_navigation_records_unique_recents_and_retains_pending_edits(self):
        editor = self.open_destination()
        editor.stage_values({'gold': 12345})
        before = (dict(editor.changes), [dict(item) for item in editor.history])
        retained = {}
        for language in ('English', 'Deutsch'):
            self.app.language_choice.set(language)
            self.app.change_language()
            for key in ('editing_presets', 'research_lab', 'workflow_builder'):
                with self.subTest(language=language, tool=key):
                    getattr(self.app, 'show_' + key)()
                    self.root.update()
                    self.assertEqual(self.app.shell_settings.recent[0], 'tool:' + key)
                    self.assertEqual(self.app.shell_settings.recent.count('tool:' + key), 1)
                    self.assertEqual(self.app.breadcrumb.get(), self.app.tr(key))
                    tool = getattr(self.app, key)
                    self.assertTrue(tool.frame.winfo_ismapped())
                    if key in retained:
                        self.assertIs(tool, retained[key])
                    retained[key] = tool
                    self.assertEqual((editor.changes, editor.history), before)
                    self.assertEqual(editor.document.source.read_bytes(), editor.document.raw)
        self.app.workflow_builder.close()

    def test_menu_reaches_retained_research_and_presets_and_preserves_editor(self):
        editor = self.open_destination()
        editor.stage_values({'gold': 12345})
        before = (dict(editor.changes), list(editor.history))
        self.app.editing_tools_menu.invoke(0)
        presets = self.app.editing_presets
        self.root.update()
        self.assertTrue(presets.frame.winfo_ismapped())
        self.assertIn(editor, presets._sessions.values())
        self.app.editing_tools_menu.invoke(3)
        research = self.app.research_lab
        self.root.update()
        self.assertTrue(research.frame.winfo_ismapped())
        self.assertFalse(presets.frame.winfo_ismapped())
        with patch.object(research, 'apply_theme', wraps=research.apply_theme) as research_theme, \
                patch.object(presets, 'apply_theme', wraps=presets.apply_theme) as preset_theme:
            for theme in ('Dark', 'Light'):
                self.app.apply_theme(theme)
            self.assertEqual(research_theme.call_count, 2)
            self.assertEqual(preset_theme.call_count, 2)
        self.app.show_library()
        self.app.show_research_lab()
        self.assertIs(self.app.research_lab, research)
        self.app.show_editing_presets()
        self.assertIs(self.app.editing_presets, presets)
        self.assertIs(self.app.select_game('origins'), editor)
        self.assertEqual((editor.changes, editor.history), before)
        self.assertEqual(editor.document.source.read_bytes(), editor.document.raw)
        self.assertEqual(VERSION, '2.7')

    def test_transfer_requires_open_destination_then_uses_that_exact_editor(self):
        with patch('tkinter.messagebox.showinfo') as info:
            self.assertIsNone(self.app.show_transfer())
            info.assert_called_once()
        editor = self.open_destination()
        dialog = self.app.show_transfer()
        self.assertIs(dialog.editor, editor)
        self.assertEqual((editor.changes, editor.history), ({}, []))
        dialog.close()

    def test_presets_and_populated_research_actions_remain_reachable_at_actual_minimum(self):
        from koei_editor.games.deception4_ps3 import parser
        from koei_editor.shared import compatible_presets
        from koei_editor.shared.preset_library import PresetLibrary
        from tests.test_ps3_new_families import fixture as research_fixture
        from tests import test_ps3_expansion

        editor = self.open_destination()
        editor.stage_values({'gold': 12345})
        before = (dict(editor.changes), [dict(item) for item in editor.history], editor.document.raw)
        presets = self.app.show_editing_presets()
        presets.library = PresetLibrary(self.folder / 'presets')
        entry = presets.library.save(compatible_presets.create(editor.adapter, editor.document,
                                      {'gold': 67890}, 'Minimum-window preview'))
        research = self.app.show_research_lab()
        first, second = self.folder / 'first.bin', self.folder / 'second.bin'
        first_raw = research_fixture(parser)
        second_raw = parser.serialize(parser.decode(first_raw), {'warl': 32})
        first.write_bytes(first_raw); second.write_bytes(second_raw)
        (self.folder / 'PARAM.SFO').write_bytes(test_ps3_expansion.PS3ContextTests.metadata('NPUB31442-GAMEDATA-10'))
        research.game.set(next(label for label, game in research._games.items() if game == parser.GAME_ID))
        research.first.set(str(first)); research.second.set(str(second)); research.compare()
        deadline = time.monotonic() + 10
        while research.busy and time.monotonic() < deadline:
            self.root.update(); time.sleep(.01)
        self.assertFalse(research.busy)
        self.assertIsNotNone(research.prepared)
        comparison = research.prepared
        research.offset.set('0x20'); research.span.set('4')
        research.note_title.set('Retain observation'); research.note_observation.set('Controlled purchase')
        research.action.set('Retain controlled-action notes'); research.add_annotation()
        notes = research.annotations

        def children(widget):
            for child in widget.winfo_children():
                yield child
                yield from children(child)

        def selected(widget):
            child = widget
            while child is not self.root:
                parent = child.master
                if not child.winfo_manager() or (isinstance(parent, ttk.Notebook) and parent.select() != str(child)):
                    return False
                child = parent
            return True

        def reachable(widget):
            widget.focus_force()
            self.root.update()
            # Disabled actions are not keyboard targets yet, but must remain
            # reachable when their existing state guards enable them.
            ancestor = widget.master
            while ancestor is not self.root:
                if isinstance(ancestor, tk.Canvas):
                    bounds = tuple(map(float, ancestor.tk.splitlist(ancestor.cget('scrollregion'))))
                    top = widget.winfo_rooty() - ancestor.winfo_rooty() + ancestor.canvasy(0)
                    if len(bounds) == 4:
                        ancestor.yview_moveto(max(0, top - 8) / max(1, bounds[3] - bounds[1]))
                        self.root.update()
                ancestor = ancestor.master
            self.assertTrue(widget.winfo_ismapped(), widget.cget('text'))
            self.assertGreater(widget.winfo_width(), 1, widget.cget('text'))
            x, y = widget.winfo_rootx(), widget.winfo_rooty()
            right, bottom = x + widget.winfo_width(), y + widget.winfo_height()
            ancestor = widget.master
            while ancestor is not None:
                message = f'{widget.cget("text")} clipped by {ancestor.winfo_class()}'
                self.assertGreaterEqual(x, ancestor.winfo_rootx(), message)
                self.assertGreaterEqual(y, ancestor.winfo_rooty(), message)
                self.assertLessEqual(right, ancestor.winfo_rootx() + ancestor.winfo_width(), message)
                self.assertLessEqual(bottom, ancestor.winfo_rooty() + ancestor.winfo_height(), message)
                ancestor = ancestor.master

        for language in ('English', 'Deutsch'):
            for size in (100, 140):
                with self.subTest(language=language, text_size=size):
                    self.app.language_choice.set(language); self.app.change_language()
                    self.app.text_size_choice.set(str(size) + '%'); self.app.change_text_size()
                    self.app.show_editing_presets()
                    presets.refresh_library(entry.id)
                    self.root.update()
                    self.assertTrue(presets.prepare_preview())
                    self.root.update()
                    plan, selection = presets._plan, presets.assignments.selection()
                    self.root.geometry('780x680'); self.root.update(); self.root.update()
                    self.assertEqual((self.root.winfo_width(), self.root.winfo_height()), (780, 680))
                    self.assertTrue(presets.frame.winfo_ismapped())
                    buttons = [widget for widget in children(presets.frame)
                               if isinstance(widget, ttk.Button) and selected(widget)]
                    self.assertGreaterEqual(len(buttons), 12)
                    for widget in buttons:
                        reachable(widget)
                    self.assertIs(presets._plan, plan)
                    self.assertEqual(presets.assignments.selection(), selection)
                    self.app.show_research_lab(); self.root.update()
                    self.assertTrue(research.frame.winfo_ismapped())
                    for tab in research.tabs.tabs():
                        research.tabs.select(tab); self.root.update()
                        buttons = [widget for widget in children(research.frame)
                                   if isinstance(widget, (ttk.Button, ttk.Checkbutton)) and selected(widget)]
                        self.assertGreaterEqual(len(buttons), 6)
                        for widget in buttons:
                            reachable(widget)
                    self.assertIs(research.prepared, comparison)
                    self.assertEqual(research.annotations, notes)
                    self.assertEqual(research.action.get(), 'Retain controlled-action notes')
                    self.assertEqual((editor.changes, editor.history, editor.document.source.read_bytes()), before)
                    self.assertEqual((first.read_bytes(), second.read_bytes()), (first_raw, second_raw))

    def test_opening_retained_tools_uses_already_selected_language_and_keeps_edits(self):
        editor = self.open_destination()
        editor.stage_values({'gold': 12345})
        before = (dict(editor.changes), [dict(item) for item in editor.history])
        self.app.language_choice.set('Deutsch')
        self.app.change_language()
        retained = {}
        for _repeat in range(2):
            for key in ('editing_presets', 'research_lab', 'workflow_builder'):
                with self.subTest(workspace=key, repeat=_repeat):
                    getattr(self.app, 'show_' + key)()
                    self.root.update()
                    tool = getattr(self.app, key)
                    self.assertEqual(self.app.breadcrumb.get(), self.app.tr(key))
                    self.assertTrue(tool.frame.winfo_ismapped())
                    if key in retained:
                        self.assertIs(tool, retained[key])
                    retained[key] = tool
                    self.assertEqual((editor.changes, editor.history), before)
                    self.assertEqual(editor.document.source.read_bytes(), editor.document.raw)
        self.assertIs(self.app.select_game('origins'), editor)
        self.app.workflow_builder.close()

    def test_real_palette_routes_retain_workspaces_and_never_change_staged_edits(self):
        editor = self.open_destination()
        editor.stage_values({'gold': 12345})
        before = (dict(editor.changes), [dict(item) for item in editor.history])
        self.app.language_choice.set('Deutsch')
        self.app.change_language()
        retained = {}
        for _repeat in range(2):
            for key in ('editing_presets', 'research_lab', 'workflow_builder', 'transfer'):
                with self.subTest(command=key, repeat=_repeat):
                    if key == 'transfer':
                        self.app.select_game('origins')
                    prior_windows = set(self.root.winfo_children())
                    self.app.open_command_palette()
                    palette = self.app.command_palette
                    command_id = 'tool:' + key
                    palette.query.set(self.app.tr(key))
                    self.root.update()
                    self.assertIn(command_id, {entry.id for entry in palette.matches})
                    palette.results.selection_set(command_id)
                    palette.activate()
                    self.root.update()
                    self.assertFalse(palette.window.winfo_exists())
                    if key == 'transfer':
                        dialogs = [window for window in self.root.winfo_children()
                                   if window not in prior_windows and isinstance(window, tk.Toplevel)]
                        self.assertEqual(len(dialogs), 1)
                        self.assertEqual(dialogs[0].title(), 'Selective Save-to-Save Transfer')
                        dialogs[0].destroy()
                    else:
                        tool = getattr(self.app, key)
                        self.assertTrue(tool.frame.winfo_ismapped())
                        self.assertEqual(self.app.breadcrumb.get(), self.app.tr(key))
                        if key in retained:
                            self.assertIs(tool, retained[key])
                        retained[key] = tool
                    self.assertEqual(self.app.shell_settings.recent[0], command_id)
                    self.assertEqual((editor.changes, editor.history), before)
                    self.assertEqual(editor.document.source.read_bytes(), editor.document.raw)
        self.assertIs(self.app.select_game('origins'), editor)
        self.app.workflow_builder.close()

    def test_root_close_respects_busy_research_and_target_editor_dirty_guard(self):
        research = self.app.show_research_lab()
        research.busy = True
        with patch('tkinter.messagebox.showinfo') as info, patch.object(self.root, 'destroy') as destroy:
            self.app.close()
            info.assert_called_once()
            destroy.assert_not_called()
        research.busy = False
        presets = self.app.show_editing_presets()
        with patch.object(presets, 'dirty_ok', return_value=False) as guard, \
                patch.object(self.root, 'destroy') as destroy:
            self.app.close()
            guard.assert_called_once()
            destroy.assert_not_called()
        with patch.object(presets, 'dirty_ok', return_value=True), \
                patch.object(presets, 'close') as close, patch.object(self.root, 'destroy') as destroy:
            self.app.close()
            close.assert_called_once()
            destroy.assert_called_once()


if __name__ == '__main__':
    unittest.main()
