"""Real Tk callbacks exercise game switching and isolated retained sessions."""
import os
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from koei_editor.application import Application
from koei_editor.game_registry import GAMES
import koei_editor.games.dw3.gui as gui
import koei_editor.games.origins.origins_gui as origins_gui
from koei_editor.games.dw3.models import Change


def widget_texts(widget, *, mapped_only=False):
    """Read actual Tk text, including labels backed by StringVars and headings."""
    texts = []
    if not mapped_only or widget.winfo_ismapped():
        options = widget.keys()
        if 'text' in options:
            texts.append(str(widget.cget('text')))
        if 'textvariable' in options and widget.cget('textvariable'):
            texts.append(str(widget.getvar(widget.cget('textvariable'))))
        if isinstance(widget, tk.Toplevel):
            texts.append(widget.title())
        if isinstance(widget, ttk.Treeview):
            texts.extend(widget.heading(column, 'text') for column in widget.cget('columns'))
        if isinstance(widget, ttk.Notebook):
            texts.extend(widget.tab(tab, 'text') for tab in widget.tabs())
    for child in widget.winfo_children():
        texts.extend(widget_texts(child, mapped_only=mapped_only))
    return texts


def widgets_of_type(widget, kind):
    if isinstance(widget, kind):
        yield widget
    for child in widget.winfo_children():
        yield from widgets_of_type(child, kind)


REMOVED_UI_PHRASES = (
    'Research & Planned Games', 'Game Mechanics', 'published', 'verified',
    'verification', 'qualification', 'independent sample', 'development',
)


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'A graphical display is required.')
class UniversalGuiTests(unittest.TestCase):
    def setUp(self):
        area = PROJECT / '.test-runs'
        area.mkdir(exist_ok=True)
        self.preference_folder = tempfile.TemporaryDirectory(dir=area)
        self.addCleanup(self.preference_folder.cleanup)
        self.preferences_path = Path(self.preference_folder.name) / 'preferences.json'
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = Application(self.root, preferences_path=self.preferences_path)

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_selector_initializes_both_games_with_isolated_sessions(self):
        self.assertIsNone(self.app.active_game)
        self.assertEqual(set(self.app.game_buttons), {game.id for game in GAMES})
        dw3 = self.app.select_game('dw3')
        origins = self.app.select_game('origins')
        self.assertIsInstance(dw3, gui.Editor)
        from koei_editor.games.origins.origins_game_editor import Editor as OriginsEditor
        self.assertIsInstance(origins, OriginsEditor)
        self.assertIsNot(dw3.changes, origins.changes)
        self.assertIsNone(dw3.document)
        self.assertIsNone(origins.document)
        self.assertEqual(set(dw3.tabs), {'Dashboard', 'Completion Companion', 'Officers', 'Items',
                                         'Weapons', 'Bodyguards', 'Unlocks', 'Collections', 'Musou Saves'})
        self.assertFalse(origins.fields.get_children())

    def test_additional_native_profiles_use_their_registered_backend_and_retain_sessions(self):
        from koei_editor.game_registry import get_game
        sessions = {}
        expected = {'atelier_ryza_switch': 'Nintendo Switch',
                    'dw8xl_ps3': 'PlayStation 3', 'dqb2_pc': 'Windows PC',
                    'atelier_ryza2_switch': 'Nintendo Switch', 'dqb2_switch': 'Nintendo Switch',
                    'p5strikers_switch': 'Nintendo Switch', 'rotk2_dos': 'DOS PC'}
        for game_id, platform in expected.items():
            with self.subTest(game=game_id):
                game = get_game(game_id)
                self.assertEqual(game.platform, platform)
                editor = self.app.select_game(game_id)
                self.assertEqual(editor.game_id, game_id)
                self.assertEqual(game.get_scalar_adapter().get_format().id, game_id)
                self.assertIsNone(editor.document)
                self.assertFalse(editor.changes)
                sessions[game_id] = editor
        self.app.apply_theme('Dark')
        self.app.show_library()
        for game_id, editor in sessions.items():
            self.assertIs(self.app.select_game(game_id), editor)
            self.assertEqual(editor.theme_name.get(), 'Dark')

    def test_switching_and_theme_changes_retain_pending_edits_and_form_values(self):
        dw3 = self.app.select_game('dw3')
        change = Change('officer', 0, 'SPoint', 999)
        dw3.changes = {('officer', 0, 'SPoint'): change}
        dw3.history = [{}]
        dw3.item_filter.set('Peacock')
        dw3.item_value.set('12')
        dw3.notebook.select(dw3.tabs['Items'])
        self.app.select_game('origins')
        self.app.apply_theme('Dark')
        self.app.show_library()
        self.assertIs(self.app.select_game('dw3'), dw3)
        self.assertEqual(dw3.theme_name.get(), 'Dark')
        self.assertEqual(dw3.item_filter.get(), 'Peacock')
        self.assertEqual(dw3.item_value.get(), '12')
        self.assertEqual(dw3.notebook.select(), str(dw3.tabs['Items']))
        self.assertEqual(list(dw3.changes.values()), [change])
        self.assertEqual(dw3.history, [{}])
        self.assertFalse(self.app.sessions['origins'][1].changes)
        dw3.apply_theme('Light')
        self.assertEqual(self.app.theme_name.get(), 'Light')
        self.assertEqual(self.app.sessions['origins'][1].theme_name.get(), 'Light')

    def test_shortcuts_dispatch_only_to_visible_game(self):
        dw3 = self.app.select_game('dw3')
        origins = self.app.select_game('origins')
        with patch.object(dw3, 'open') as first, patch.object(origins, 'open') as second:
            self.app.dispatch('open')
            first.assert_not_called()
            second.assert_called_once()
            self.app.show_library()
            self.app.dispatch('open')
            self.assertEqual(second.call_count, 1)

    def test_close_checks_hidden_dw3_pending_edits_and_honors_cancel(self):
        dw3 = self.app.select_game('dw3')
        self.app.select_game('origins')
        with patch.object(dw3, 'dirty_ok', return_value=False) as confirm, patch.object(self.root, 'destroy') as destroy:
            self.app.close()
            confirm.assert_called_once()
            destroy.assert_not_called()

    def test_origins_open_backup_compare_export_save_copy_and_restore_callbacks(self):
        # Opaque copy tooling remains source-only. Its callbacks are tested
        # directly, without registering it as a gameplay library session.
        host = ttk.Frame(self.root)
        editor = origins_gui.Editor(self.root, parent=host)
        raw = bytes(range(256)) * 4
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'SLOT0001.dat'
            after = Path(folder) / 'SLOT0002.dat'
            source.write_bytes(raw)
            after.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
            with patch.object(origins_gui.filedialog, 'askopenfilename', return_value=str(source)):
                editor.open()
            self.assertEqual(editor.backup.read_bytes(), raw)
            self.assertIn('Unverified file', editor.summary.get())
            with patch.object(origins_gui.filedialog, 'askopenfilename', return_value=str(after)):
                editor.compare()
            self.assertEqual(editor.comparison['changed_bytes'], 1)
            target = Path(folder) / 'same-copy.dat'
            with patch.object(origins_gui.filedialog, 'asksaveasfilename', return_value=str(target)):
                editor.save_as()
            self.assertEqual(target.read_bytes(), raw)
            restored = Path(folder) / 'restored.dat'
            with patch.object(origins_gui.filedialog, 'askopenfilename', return_value=str(editor.backup)), \
                    patch.object(origins_gui.filedialog, 'asksaveasfilename', return_value=str(restored)):
                editor.restore()
            self.assertEqual(restored.read_bytes(), raw)
            report = Path(folder) / 'result.changes.json'
            with patch.object(origins_gui.filedialog, 'asksaveasfilename', return_value=str(report)):
                editor.export()
            self.assertTrue(report.is_file())
            self.assertEqual(source.read_bytes(), raw)
            self.assertEqual(after.read_bytes(), raw[:-1] + bytes([raw[-1] ^ 1]))

    def test_failed_origins_open_preserves_previous_session(self):
        import koei_editor.shared.verified_gui as verified_gui
        editor = self.app.select_game('origins')
        original = object()
        editor.document = original
        with patch.object(verified_gui.filedialog, 'askopenfilename', return_value='wrong.sav'), \
                patch.object(verified_gui.messagebox, 'showerror') as error:
            editor.open()
            error.assert_called_once()
        self.assertIs(editor.document, original)

    def test_native_origins_staging_max_undo_review_save_restore_and_user_rejection(self):
        from tests.test_origins_parser import fixture
        import koei_editor.games.origins.origins_codec as origins_codec
        import koei_editor.games.origins.origins_parser as origins_parser
        import koei_editor.shared.verified_gui as verified_gui
        editor = self.app.select_game('origins')
        area = PROJECT / '.test-runs'
        area.mkdir(exist_ok=True)
        raw = fixture()
        user_raw = origins_codec.encode(bytes(origins_codec.USER_FILE_SIZE - 4), 9, 'user')
        with tempfile.TemporaryDirectory(dir=area) as folder:
            source = Path(folder) / 'SLOT0000.dat'
            user = Path(folder) / 'USER.dat'
            source.write_bytes(raw)
            user.write_bytes(user_raw)
            with patch.object(verified_gui.filedialog, 'askopenfilename', return_value=str(source)), \
                    patch.object(verified_gui.messagebox, 'showerror') as error:
                editor.open()
                error.assert_not_called()
            opened = editor.document
            snapshot = editor.backup
            self.assertEqual(snapshot.read_bytes(), raw)
            editor.group.set('Resources')
            editor.refresh()
            self.assertEqual(set(editor.fields.get_children()), {'gold', 'skill_points', 'dlc_skill_points'})
            editor.fields.selection_set('gold')
            editor.value.set('77777')
            editor.apply_selected()
            self.assertEqual(editor.changes, {'gold': 77777})
            self.app.select_game('dw3')
            self.app.apply_theme('Dark')
            self.assertIs(self.app.select_game('origins'), editor)
            self.assertIs(editor.document, opened)
            self.assertEqual(editor.value.get(), '77777')
            editor.max_visible()
            self.assertEqual(editor.changes, {'gold': 999999, 'skill_points': 999, 'dlc_skill_points': 999})
            self.assertEqual(len(editor.history), 2)
            editor.undo()
            self.assertEqual(editor.changes, {'gold': 77777})
            editor.fields.selection_set(('gold', 'skill_points', 'dlc_skill_points'))
            editor.max_selected()
            pending = dict(editor.changes)
            history = list(editor.history)
            self.assertEqual(pending, {'gold': 999999, 'skill_points': 999, 'dlc_skill_points': 999})
            self.assertEqual(origins_parser.field_map(opened)['gold'].value(opened.payload), 3456)
            editor.review()
            editor.show_inspector()
            texts = '\n'.join(widget_texts(self.root))
            self.assertIn('Review Changes', texts)
            rows = [view.item(key, 'values') for view in widgets_of_type(self.root, ttk.Treeview)
                    for key in view.get_children()]
            self.assertIn(('Gold', '3,456', '999,999'), rows)
            self.assertIn(('DLC Skill Points', '20', '999'), rows)
            self.assertIn(('Format', 'Native slot revision', '29'), rows)
            # A valid system envelope must fail the gameplay slot parser without
            # discarding the active document, pending edits or Undo history.
            with patch.object(verified_gui.filedialog, 'askopenfilename', return_value=str(user)), \
                    patch.object(verified_gui.messagebox, 'showerror') as error:
                editor.open()
                error.assert_called_once()
                self.assertIn('USER.dat', str(error.call_args))
            self.assertIs(editor.document, opened)
            self.assertEqual(editor.changes, pending)
            self.assertEqual(editor.history, history)
            target = Path(folder) / 'edited.dat'
            with patch.object(verified_gui.filedialog, 'asksaveasfilename', return_value=str(target)), \
                    patch.object(verified_gui.messagebox, 'showerror') as error:
                editor.save_as()
                error.assert_not_called()
            reopened = origins_parser.read_save(target)
            self.assertEqual(origins_parser.field_map(reopened)['gold'].value(reopened.payload), 999999)
            self.assertEqual(origins_parser.field_map(reopened)['skill_points'].value(reopened.payload), 999)
            self.assertEqual(origins_parser.field_map(reopened)['dlc_skill_points'].value(reopened.payload), 999)
            self.assertFalse(editor.changes)
            self.assertFalse(editor.history)
            restored = Path(folder) / 'restored.dat'
            with patch.object(verified_gui.filedialog, 'askopenfilename', return_value=str(snapshot)), \
                    patch.object(verified_gui.filedialog, 'asksaveasfilename', return_value=str(restored)), \
                    patch.object(verified_gui.messagebox, 'showerror') as error:
                editor.restore()
                error.assert_not_called()
            self.assertEqual(restored.read_bytes(), raw)
            self.assertEqual(source.read_bytes(), raw)
            self.assertEqual(user.read_bytes(), user_raw)

    def test_native_origins_dynamic_groups_search_and_nonmaxable_training(self):
        from tests.test_origins_integration import mapped_fixture
        import koei_editor.shared.verified_gui as verified_gui
        editor = self.app.select_game('origins')
        raw = mapped_fixture(29)
        editor.document = editor.adapter.decode(raw)
        editor.refresh()
        self.assertTrue({'Existing bonds', 'Bond training', 'Provincial peace', 'Weapons', 'Battle clear history'}
                        <= set(editor.group_selector.cget('values')))
        editor.stage_values({'gold': 77777})
        editor.group.set('Bond training')
        editor.search.set('7 training')
        self.assertEqual(editor.fields.get_children(), ('bond_7_training',))
        editor.max_visible()
        self.assertEqual(editor.changes, {'gold': 77777})
        self.assertEqual(len(editor.history), 1)
        editor.fields.selection_set('bond_7_training')
        editor.selected()
        self.assertIn('excluded from Max', editor.selection_info.get())
        editor.value.set('3')
        editor.apply_selected()
        editor.group.set('Weapons')
        editor.search.set('weapon 0043')
        self.assertEqual(editor.fields.get_children(), ('weapon_0043_upgrade',))
        editor.max_visible()
        self.assertEqual(editor.changes['weapon_0043_upgrade'], 99)
        self.assertEqual(editor.changes['bond_7_training'], 3)
        editor.group.set('Existing bonds')
        editor.search.set('7 level')
        editor.max_visible()
        self.assertEqual(editor.changes['bond_7_level'], 5)
        editor.undo()
        self.assertNotIn('bond_7_level', editor.changes)
        editor.group.set('Provincial peace')
        editor.search.set('8 peace')
        self.assertEqual(editor.fields.get_children(), ('peace_8',))
        editor.max_visible()
        expected = {'gold': 77777, 'bond_7_training': 3,
                    'weapon_0043_upgrade': 99, 'peace_8': 10000}
        self.assertEqual(editor.changes, expected)
        self.app.select_game('pw3')
        self.app.apply_theme('Dark')
        self.assertIs(self.app.select_game('origins'), editor)
        self.assertEqual(editor.search.get(), '8 peace')
        self.assertEqual(editor.fields.get_children(), ('peace_8',))
        self.assertEqual(editor.changes, expected)
        with patch.object(verified_gui.messagebox, 'showerror') as error:
            editor.stage_values({'weapon_0043_upgrade': 99, 'bond_7_level': 0})
            error.assert_called_once()
        self.assertEqual(editor.changes, expected)
        editor.group.set('Battle clear history')
        editor.search.set('battle_history 68')
        self.assertEqual(editor.fields.get_children(), ('battle_history_68',))
        history_length = len(editor.history)
        editor.max_visible()
        self.assertEqual(len(editor.history), history_length)
        self.assertEqual(editor.changes, expected)
        editor.fields.selection_set('battle_history_68')
        editor.max_selected()
        self.assertEqual(editor.changes, expected)
        editor.value.set('1')
        editor.apply_selected()
        self.assertEqual(editor.changes, expected | {'battle_history_68': 1})
        editor.search.set('battle_history_0')
        self.assertEqual(editor.fields.get_children(), ('battle_history_0',))
        editor.fields.selection_set('battle_history_0')
        editor.value.set('0')
        with patch.object(verified_gui.messagebox, 'showerror') as error:
            editor.apply_selected()
            error.assert_called_once()
        self.assertEqual(editor.changes, expected | {'battle_history_68': 1})
        editor.undo()
        self.assertEqual(editor.changes, expected)
        editor.group.set('Weapons')
        editor.search.set('weapon 0046')
        self.assertEqual(editor.fields.get_children(), ('weapon_0046_upgrade',))
        editor.fields.selection_set('weapon_0046_upgrade')
        editor.selected()
        self.assertEqual(editor.value.get(), '0')
        editor.max_selected()
        self.assertEqual(editor.changes, expected | {'weapon_0046_upgrade': 99})
        self.assertEqual(editor.document.raw, raw)

    def test_contact_dialog_uses_existing_author_branding(self):
        self.app.apply_theme('Dark')
        self.app.contact()
        dialog = next(widget for widget in self.root.winfo_children() if isinstance(widget, tk.Toplevel))
        self.assertEqual(dialog.title(), 'Contact Mexican')

    def test_pc_scalar_editors_open_stage_undo_switch_review_and_save_as(self):
        from tests.test_verified_editors import synthetic_raw
        import koei_editor.shared.verified_editor as backend
        import koei_editor.shared.verified_gui as verified_gui
        for game_id, key in (('dw8xl', 'gold'), ('pw3', 'character_0_attack')):
            editor = self.app.select_game(game_id)
            with tempfile.TemporaryDirectory() as folder:
                source = Path(folder)/'save.dat'
                raw = synthetic_raw(game_id)
                source.write_bytes(raw)
                with patch.object(verified_gui.filedialog, 'askopenfilename', return_value=str(source)), \
                        patch.object(verified_gui.messagebox, 'showerror') as error:
                    editor.open()
                    error.assert_not_called()
                self.assertEqual(editor.backup.read_bytes(), raw)
                self.assertEqual(editor.status.get(), 'Opened save copy. Automatic backup: ' + editor.backup.name)
                self.assertEqual(len(editor.fields.get_children()), len(editor.layout.fields))
                editor.fields.selection_set(key)
                editor.value.set('123')
                editor.apply_selected()
                self.assertEqual(editor.changes[key], 123)
                editor.undo()
                self.assertFalse(editor.changes)
                editor.value.set('321')
                editor.apply_selected()
                self.app.select_game('dw3')
                self.app.apply_theme('Dark')
                self.assertIs(self.app.select_game(game_id), editor)
                self.assertEqual(editor.changes[key], 321)
                editor.review()
                target = Path(folder)/'edited.dat'
                with patch.object(verified_gui.filedialog, 'asksaveasfilename', return_value=str(target)), \
                        patch.object(verified_gui.messagebox, 'showerror') as error:
                    editor.save_as()
                    error.assert_not_called()
                self.assertEqual(backend.field_map(editor.document)[key].value(editor.document.payload), 321)
                self.assertFalse(editor.changes)
                self.assertEqual(source.read_bytes(), raw)
                restored = Path(folder)/'restored.dat'
                with patch.object(verified_gui.filedialog, 'askopenfilename', return_value=str(editor.backup)), \
                        patch.object(verified_gui.filedialog, 'asksaveasfilename', return_value=str(restored)), \
                        patch.object(verified_gui.messagebox, 'showerror') as error:
                    editor.restore()
                    error.assert_not_called()
                self.assertEqual(restored.read_bytes(), raw)

    def test_scalar_max_visible_is_one_undoable_batch_and_invalid_batch_is_atomic(self):
        from tests.test_verified_editors import synthetic_raw
        import koei_editor.shared.verified_editor as backend
        import koei_editor.shared.verified_gui as verified_gui
        editor = self.app.select_game('pw3')
        editor.document = backend.decode(synthetic_raw('pw3'), 'pw3')
        editor.group.set('Characters')
        editor.refresh()
        editor.max_visible()
        self.assertEqual(len(editor.history), 1)
        self.assertNotIn('beli', editor.changes)
        editor.undo()
        self.assertFalse(editor.changes)
        with patch.object(verified_gui.messagebox, 'showerror') as error:
            editor.stage_values({'character_0_attack':100, 'character_0_special':100})
            error.assert_called_once()
        self.assertFalse(editor.changes)
        self.assertFalse(editor.history)

    def test_scalar_search_tokens_group_scope_max_visible_and_hidden_edits_survive_switch(self):
        from tests.test_verified_editors import synthetic_raw
        import koei_editor.shared.verified_editor as verified_editor
        editor = self.app.select_game('dw8xl')
        raw = synthetic_raw('dw8xl')
        editor.document = verified_editor.decode(raw, 'dw8xl')
        editor.refresh()
        editor.stage_values({'gold': 123})
        editor.group.set('Officers')
        query = 'oFFicer SlOT 01 AtTaCK'
        editor.search.set(query)
        self.assertEqual(editor.fields.get_children(), ('officer_0_attack',))
        self.assertEqual(editor.changes, {'gold': 123})
        editor.max_visible()
        self.assertEqual(editor.changes, {'gold': 123, 'officer_0_attack': 1500})
        self.assertEqual(len(editor.history), 2)
        editor.undo()
        self.assertEqual(editor.changes, {'gold': 123})
        self.app.select_game('pw3')
        self.app.apply_theme('Dark')
        self.assertIs(self.app.select_game('dw8xl'), editor)
        self.assertEqual(editor.search.get(), query)
        self.assertEqual(editor.fields.get_children(), ('officer_0_attack',))
        editor.search.set('no matching record')
        self.assertFalse(editor.fields.get_children())
        editor.max_visible()
        self.assertEqual(editor.changes, {'gold': 123})
        self.assertEqual(len(editor.history), 1)
        editor.group.set('All fields')
        editor.search.set('resources GOLD')
        self.assertEqual(editor.fields.get_children(), ('gold',))
        editor.search.set('')
        self.assertEqual(len(editor.fields.get_children()), len(editor.adapter.fields_for(editor.document)))
        self.assertEqual(editor.document.raw, raw)

    def test_dw4_candidate_uses_own_backend_copy_workflow_and_retains_session(self):
        from tests.test_dw4hyper_format import procedural_raw
        import koei_editor.games.dw4hyper.dw4hyper_parser as candidate
        import koei_editor.shared.verified_gui as verified_gui
        editor = self.app.select_game('dw4hyper')
        self.assertIs(editor.backend, candidate)
        self.assertIn('dw4hyper', self.app.game_buttons)
        self.assertEqual(editor.subtitle, 'Windows PC save editor')
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'save.dat'
            raw = procedural_raw()
            source.write_bytes(raw)
            with patch.object(verified_gui.filedialog, 'askopenfilename', return_value=str(source)), \
                    patch.object(verified_gui.messagebox, 'showerror') as error:
                editor.open()
                error.assert_not_called()
            self.assertEqual(editor.backup.read_bytes(), raw)
            self.assertEqual(editor.status.get(), 'Opened save copy. Automatic backup: ' + editor.backup.name)
            self.assertEqual(set(editor.fields.get_children()), set(editor.adapter.field_map(editor.document)))
            self.assertIn('officer_0_harness', editor.fields.get_children())
            self.assertEqual(editor.fields.item('officer_0_attack')['values'][0], 'Zhao Yun')
            editor.fields.selection_set('officer_0_weapon_experience')
            editor.selected()
            self.assertIn('no Lv.11', editor.selection_info.get())
            editor.fields.selection_set('officer_0_attack')
            editor.value.set('99')
            editor.apply_selected()
            self.assertEqual(editor.changes, {'officer_0_attack': 99})
            editor.undo()
            self.assertFalse(editor.changes)
            editor.group.set('Officers')
            editor.refresh()
            editor.max_visible()
            self.assertTrue(all(key.endswith('_unlocked') for key in editor.changes))
            editor.undo()
            editor.stage_values({'officer_0_attack': 99, 'item_0': 20})
            self.app.select_game('pw3')
            self.app.apply_theme('Dark')
            self.assertIs(self.app.select_game('dw4hyper'), editor)
            self.assertEqual(editor.theme_name.get(), 'Dark')
            editor.show_inspector()
            editor.review()
            target = Path(folder) / 'edited.dat'
            with patch.object(verified_gui.filedialog, 'asksaveasfilename', return_value=str(target)), \
                    patch.object(verified_gui.messagebox, 'showerror') as error:
                editor.save_as()
                error.assert_not_called()
            self.assertEqual(candidate.field_map(editor.document)['officer_0_attack'].value(editor.document.payload), 99)
            self.assertEqual(candidate.field_map(editor.document)['item_0'].value(editor.document.payload), 20)
            self.assertFalse(editor.changes)
            self.assertEqual(source.read_bytes(), raw)

    def test_dw4_candidate_minimum_window_preserves_status_and_selected_field_hint(self):
        from tests.test_dw4hyper_format import procedural_raw
        import koei_editor.games.dw4hyper.dw4hyper_parser as dw4hyper_parser
        editor = self.app.select_game('dw4hyper')
        editor.workspace_tabs.select(editor.edit_page)
        editor.document = dw4hyper_parser.decode(procedural_raw())
        editor.refresh()
        editor.fields.selection_set('officer_0_attack')
        editor.selected()
        self.root.deiconify()
        self.root.geometry('1080x820')
        self.root.update()
        for label in (editor.selection_label, editor.status_label):
            self.assertTrue(label.winfo_ismapped())
            bottom = label.winfo_rooty() + label.winfo_height()
            self.assertLessEqual(bottom, self.root.winfo_rooty() + self.root.winfo_height())
            self.assertGreaterEqual(label.winfo_height(), label.winfo_reqheight())

    def test_sophie2_shared_gui_copy_edits_max_undo_review_inspect_and_restore(self):
        from tests.test_atelier_sophie2_format import procedural_raw
        import koei_editor.games.sophie2.atelier_sophie2_parser as backend
        import koei_editor.shared.verified_gui as verified_gui
        self.app.game_buttons['atelier_sophie2'].invoke()
        editor = self.app.sessions['atelier_sophie2'][1]
        self.assertIs(editor.backend, backend)
        frame = self.app.sessions['atelier_sophie2'][0]

        def invoke(label):
            button = next(button for button in widgets_of_type(frame, ttk.Button)
                          if button.cget('text') == label)
            self.assertNotIn('disabled', button.state())
            button.invoke()

        def edit(key, value):
            editor.fields.selection_set(key)
            editor.selected()
            editor.value.set(str(value))
            invoke('Apply Selected')
            editor.selected()

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'data.dat'
            raw = procedural_raw()
            source.write_bytes(raw)
            with patch.object(verified_gui.filedialog, 'askopenfilename', return_value=str(source)), \
                    patch.object(verified_gui.messagebox, 'showerror') as error:
                invoke('Open Save Copy')
                error.assert_not_called()
            self.assertEqual(editor.backup.read_bytes(), raw)
            self.assertEqual(len(editor.fields.get_children()), 14)
            group_selector = editor.group_selector
            self.assertIn(group_selector, tuple(widgets_of_type(frame, ttk.Combobox)))
            self.assertIn('Material container', group_selector.cget('values'))
            self.assertIn('Alchemy', group_selector.cget('values'))
            self.assertIn('Sophie equipment', group_selector.cget('values'))
            self.assertNotIn('Consumable container', group_selector.cget('values'))

            edit('materials_0_quality', 777)
            self.assertEqual(editor.changes, {'materials_0_quality': 777})
            invoke('Undo')
            self.assertFalse(editor.changes)
            editor.group.set('Material container')
            editor.refresh()
            invoke('Max Visible Fields')
            self.assertEqual(editor.changes, {'materials_0_quality': 999})
            self.assertNotIn('materials_1_quality', editor.changes)
            invoke('Undo')

            editor.group.set('Alchemy')
            editor.refresh()
            edit('sophie_exp', 3456)
            self.assertIn('storage bound', editor.selection_info.get())
            self.assertIn('Excluded from Max', editor.selection_info.get())
            for phrase in REMOVED_UI_PHRASES:
                self.assertNotIn(phrase.lower(), editor.selection_info.get().lower())
            invoke('Max Selected')
            invoke('Max Visible Fields')
            self.assertEqual(editor.changes, {'sophie_exp': 3456})
            self.assertEqual(len(editor.history), 1)
            invoke('Undo')
            self.assertFalse(editor.changes)

            editor.group.set('All fields')
            editor.refresh()
            edit('materials_0_quality', 777)
            edit('sophie_exp', 3456)
            self.app.select_game('dw3')
            self.app.apply_theme('Dark')
            self.assertIs(self.app.select_game('atelier_sophie2'), editor)
            self.assertEqual(editor.theme_name.get(), 'Dark')
            self.assertEqual(editor.changes, {'materials_0_quality': 777, 'sophie_exp': 3456})
            invoke('Review Changes')
            review = next(dialog for dialog in self.root.winfo_children()
                          if isinstance(dialog, tk.Toplevel) and dialog.title() == 'Review Changes')
            tree = next(widgets_of_type(review, ttk.Treeview))
            self.assertEqual(len(tree.get_children()), 2)
            self.assertEqual({str(tree.item(key)['values'][2]) for key in tree.get_children()}, {'777', '3,456'})
            review.destroy()
            invoke('Inspect Data')
            inspector = next(dialog for dialog in self.root.winfo_children()
                             if isinstance(dialog, tk.Toplevel) and 'Read Only' in dialog.title())
            inspected = [tree.item(key)['values'] for tree in widgets_of_type(inspector, ttk.Treeview)
                         for key in tree.get_children()]
            self.assertEqual(len(inspected), 15 + len(backend.item_records(editor.document)))
            self.assertEqual({row[0] for row in inspected}, {'Alchemy', 'Resources', 'Inventory', 'Equipment'}
                             | {row['group'] for row in backend.item_records(editor.document)})
            self.assertTrue(any('m_mixGem' in str(row) and str(row[-1]) == '4' for row in inspected))
            inspector.destroy()

            target = Path(folder) / 'edited.dat'
            with patch.object(verified_gui.filedialog, 'asksaveasfilename', return_value=str(target)), \
                    patch.object(verified_gui.messagebox, 'showerror') as error:
                invoke('Save As...')
                error.assert_not_called()
            output = backend.read_save(target)
            self.assertEqual(backend.field_map(output)['materials_0_quality'].value(output.payload), 777)
            self.assertEqual(backend.field_map(output)['sophie_exp'].value(output.payload), 3456)
            self.assertEqual(backend.field_map(output)['materials_1_quality'].value(output.payload), 1200)
            self.assertFalse(editor.changes)
            self.assertEqual(source.read_bytes(), raw)
            restored = Path(folder) / 'restored.dat'
            with patch.object(verified_gui.filedialog, 'askopenfilename', return_value=str(editor.backup)), \
                    patch.object(verified_gui.filedialog, 'asksaveasfilename', return_value=str(restored)), \
                    patch.object(verified_gui.messagebox, 'showerror') as error:
                invoke('Restore Backup...')
                error.assert_not_called()
            self.assertEqual(restored.read_bytes(), raw)
            self.assertEqual(source.read_bytes(), raw)

    def test_self_test_reports_native_profile_without_claiming_game_load(self):
        from tests.test_dw4hyper_format import procedural_raw
        from koei_editor.shared.verified_self_test import run
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'save.dat'
            raw = procedural_raw()
            source.write_bytes(raw)
            report = run('dw4hyper', source, Path(folder) / 'test-output')
            self.assertEqual(report['fields_checked'], 415)
            self.assertTrue(report['checksum_verified'])
            self.assertTrue(report['input_preserved'])
            self.assertTrue(report['format_sample_verified'])
            self.assertTrue(report['native_integrity_verified'])
            self.assertFalse(report['in_game_load_tested'])
            self.assertEqual(source.read_bytes(), raw)

    def test_platform_filter_separates_editions_without_losing_sessions(self):
        pc = self.app.select_game('dw4hyper')
        pc.changes = {'officer_0_attack': 99}
        self.app.show_library()
        self.app.platform_choice.set('PlayStation 2')
        self.app.show_platform()
        self.root.deiconify()
        self.root.update()
        self.assertTrue(self.app.game_buttons['dw4xl_ps2'].winfo_ismapped())
        self.assertFalse(self.app.game_buttons['dw4hyper'].winfo_ismapped())
        self.assertEqual(pc.changes, {'officer_0_attack': 99})
        self.app.platform_choice.set('Windows PC')
        self.app.show_platform()
        self.root.update()
        self.assertTrue(self.app.game_buttons['dw4hyper'].winfo_ismapped())
        self.assertFalse(self.app.game_buttons['dw4xl_ps2'].winfo_ismapped())
        self.assertIs(self.app.select_game('dw4hyper'), pc)

    def test_ps2_xl_gui_copy_workflow_and_cross_platform_rejection(self):
        from tests.test_dw4xl_format import procedural_psu
        from tests.test_dw4hyper_format import procedural_raw
        import koei_editor.games.dw4xl.dw4xl_parser as dw4xl_parser
        import koei_editor.shared.verified_gui as verified_gui
        from koei_editor.game_registry import get_game
        from koei_editor.games.dw3.models import SaveError
        from koei_editor.shared.verified_self_test import run
        editor = self.app.select_game('dw4xl_ps2')
        self.assertEqual(self.app.platform_choice.get(), 'PlayStation 2')
        self.assertEqual(editor.save_extension, '.psu')
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'copy.psu'
            raw = procedural_psu()
            source.write_bytes(raw)
            with patch.object(verified_gui.filedialog, 'askopenfilename', return_value=str(source)), \
                    patch.object(verified_gui.messagebox, 'showerror') as error:
                editor.open()
                error.assert_not_called()
            self.assertEqual(set(editor.fields.get_children()), set(editor.adapter.field_map(editor.document)))
            self.assertIn('officer_0_harness', editor.fields.get_children())
            self.assertEqual(editor.status.get(), 'Opened save copy. Automatic backup: ' + editor.backup.name)
            editor.stage_values({'officer_0_attack': 99, 'item_19': 1})
            editor.undo()
            self.assertFalse(editor.changes)
            editor.stage_values({'officer_0_attack': 99, 'item_19': 1})
            editor.show_inspector()
            editor.review()
            target = Path(folder) / 'edited.psu'
            with patch.object(verified_gui.filedialog, 'asksaveasfilename', return_value=str(target)) as dialog, \
                    patch.object(verified_gui.messagebox, 'showerror') as error:
                editor.save_as()
                error.assert_not_called()
                self.assertEqual(dialog.call_args.kwargs['defaultextension'], '.psu')
            self.assertEqual(dw4xl_parser.field_map(editor.document)['officer_0_attack'].value(editor.document.payload), 99)
            self.assertEqual(source.read_bytes(), raw)
            report = run('dw4xl_ps2', source, Path(folder) / 'self-test')
            self.assertTrue(report['format_sample_verified'])
            self.assertTrue(report['backup_restored'])
            self.assertTrue((Path(folder) / 'self-test' / 'edited.psu').is_file())
            foreign = Path(folder) / 'wrong.psu'
            foreign.write_bytes(procedural_raw())
            with self.assertRaises(SaveError):
                get_game('dw4xl_ps2').read_save(foreign)
            foreign = Path(folder) / 'wrong.dat'
            foreign.write_bytes(raw)
            with self.assertRaises(SaveError):
                get_game('dw4hyper').read_save(foreign)

    def test_native_origins_card_and_removed_research_and_mechanics_screens(self):
        self.assertIn('origins', self.app.game_buttons)
        for name in ('show_research', 'show_mechanics', 'research_button', 'mechanics_button'):
            self.assertFalse(hasattr(self.app, name), name)
        texts = '\n'.join(widget_texts(self.app.library)).lower()
        for phrase in REMOVED_UI_PHRASES:
            self.assertNotIn(phrase.lower(), texts)
        self.assertFalse(any(isinstance(widget, tk.Toplevel) for widget in self.root.winfo_children()))
        self.assertNotIn('development', self.root.title().lower())
        self.assertIsNone(self.app.active_game)

    def test_minimum_window_keeps_library_actions_accessible_on_both_platforms(self):
        from koei_editor.game_registry import get_game
        self.root.deiconify()
        self.root.geometry('1080x820')
        for theme in ('Light', 'Dark'):
            self.app.apply_theme(theme)
            for platform in ('Windows PC', 'PlayStation 2'):
                self.app.platform_choice.set(platform)
                self.app.show_platform()
                self.root.update()
                self.assertIn(platform, self.app.library_hint.get())
                for game_id, button in self.app.game_buttons.items():
                    visible = get_game(game_id).platform == platform
                    canvas = self.app.platform_canvases[get_game(game_id).platform]
                    self.assertEqual(bool(canvas.winfo_ismapped()), visible)
                    if visible:
                        self.assertTrue(button.winfo_ismapped())
                        button.focus_force()
                        self.root.update()
                        canvas = self.app.platform_canvases[platform]
                        self.assertGreaterEqual(button.winfo_height(), button.winfo_reqheight())
                        self.assertGreaterEqual(button.winfo_rooty(), canvas.winfo_rooty())
                        self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                             canvas.winfo_rooty() + canvas.winfo_height())
                        for label in widgets_of_type(button.master, ttk.Label):
                            self.assertGreaterEqual(label.winfo_width(), label.winfo_reqwidth())
                            self.assertGreaterEqual(label.winfo_height(), label.winfo_reqheight())
                        button.invoke()
                        self.assertEqual(self.app.active_game, game_id)
                        self.app.show_library()
                        self.root.update()
                button = self.app.contact_button
                self.assertEqual(button.cget('text'), 'Contact Mexican')
                self.assertTrue(button.winfo_ismapped())
                self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                     self.root.winfo_rooty() + self.root.winfo_height())
                texts = '\n'.join(widget_texts(self.app.library, mapped_only=True)).lower()
                for phrase in REMOVED_UI_PHRASES:
                    self.assertNotIn(phrase.lower(), texts)

    def test_future_library_rows_scroll_focus_reveal_and_invoke_real_buttons(self):
        from dataclasses import replace
        from types import SimpleNamespace
        from koei_editor.shared.adapter_contract import SESSION_ACTIONS
        import koei_editor.game_registry as game_registry
        from koei_editor.game_registry import GAMES
        def future_session(game, root, parent, theme, on_theme):
            # This test exercises library geometry, not a falsely registered
            # PW3 parser under an invented game identity.
            return SimpleNamespace(game_id=game.id, document=None, changes={},
                                   theme_name=tk.StringVar(root, value=theme),
                                   **{name: lambda: True for name in SESSION_ACTIONS})
        expanded = GAMES + tuple(replace(GAMES[2], id=f'future_{index}',
                                        title=f'FUTURE WARRIORS {index + 1}') for index in range(7))
        future_root = tk.Tk()
        try:
            with patch('koei_editor.application.GAMES', expanded), \
                    patch.object(game_registry, 'ALL_ADAPTERS', expanded + game_registry.RESEARCH_TOOLS), \
                    patch.object(game_registry.Game, 'create_editor', new=future_session):
                app = Application(future_root, preferences_path=self.preferences_path)
                future_root.geometry('1080x820')
                future_root.update()
                canvas = app.platform_canvases['Windows PC']
                self.assertLess(canvas.yview()[1], 1.0)
                canvas.event_generate('<Button-5>', x=10, y=10)
                future_root.update()
                self.assertGreater(canvas.yview()[0], 0)
                canvas.yview_moveto(0)
                canvas.event_generate('<MouseWheel>', delta=-120, x=10, y=10)
                future_root.update()
                self.assertGreater(canvas.yview()[0], 0)
                before = canvas.yview()
                app.contact_button.event_generate('<MouseWheel>', delta=-120)
                self.assertEqual(canvas.yview(), before)
                button = app.game_buttons['future_6']
                button.focus_force()
                future_root.update()
                self.assertGreaterEqual(button.winfo_rooty(), canvas.winfo_rooty())
                self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                     canvas.winfo_rooty() + canvas.winfo_height())
                self.assertTrue(app.contact_button.winfo_ismapped())
                self.assertLessEqual(app.contact_button.winfo_rooty() + app.contact_button.winfo_height(),
                                     future_root.winfo_rooty() + future_root.winfo_height())
                before = canvas.yview()
                button.invoke()
                self.assertEqual(app.active_game, 'future_6')
                canvas.event_generate('<Button-5>', x=10, y=10)
                self.assertEqual(canvas.yview(), before)
                self.assertIs(app.select_game('future_6'), app.sessions['future_6'][1])
                app.show_library()
                app.platform_choice.set('PlayStation 2')
                app.show_platform()
                future_root.update()
                self.assertFalse(canvas.winfo_ismapped())
                self.assertTrue(app.game_buttons['dw4xl_ps2'].winfo_ismapped())
        finally:
            future_root.destroy()

    def test_read_only_pc_progression_and_data_inspection_callbacks(self):
        from tests.test_verified_editors import synthetic_raw
        import koei_editor.shared.verified_editor as backend
        editor = self.app.select_game('pw3')
        editor.document = backend.decode(synthetic_raw('pw3'),'pw3')
        editor.refresh()
        editor.fields.selection_set('character_0_attack')
        editor.selected()
        self.assertIn('level 1', editor.selection_info.get())
        self.assertIn('read only', editor.selection_info.get())
        editor.show_inspector()
        self.root.update_idletasks()
        dialogs = [widget for widget in self.root.winfo_children() if isinstance(widget, tk.Toplevel)]
        self.assertEqual(len(dialogs), 1)
        self.assertIn('Read Only', dialogs[0].title())
        self.assertIn('Progression', '\n'.join(widget_texts(dialogs[0])))
        self.assertIn('Costume associations', '\n'.join(widget_texts(dialogs[0])))
        self.assertFalse(hasattr(editor, 'show_mechanics'))

    def test_scalar_editor_keeps_editing_controls_and_removes_evidence_panels(self):
        self.root.deiconify()
        for game_id in ('dw8xl', 'pw3', 'dw4hyper', 'dw4xl_ps2', 'atelier_sophie2', 'origins'):
            editor = self.app.select_game(game_id)
            editor.workspace_tabs.select(editor.edit_page)
            self.root.update()
            frame = self.app.sessions[game_id][0]
            texts = widget_texts(frame, mapped_only=True)
            visible = '\n'.join(texts).lower()
            for phrase in REMOVED_UI_PHRASES:
                self.assertNotIn(phrase.lower(), visible, game_id)
            self.assertEqual(editor.fields.heading('limit', 'text'), 'Supported maximum')
            self.assertEqual(editor.fields.heading('storage', 'text'), 'Encoding limit')
            self.assertIn('More options', texts)
            self.assertNotIn('Experimental: allow above supported limits', texts)
            editor.options_visible.set(True)
            editor.toggle_options()
            self.root.update()
            self.assertIn('Experimental: allow above supported limits', widget_texts(frame, mapped_only=True))
            editor.options_visible.set(False)
            editor.toggle_options()
            for label in ('Open Save Copy', 'Save As...', 'Backup Save', 'Review Changes',
                          'Undo', 'Restore Backup...', 'Apply Selected', 'Max Selected',
                          'Max Visible Fields', 'Inspect Data'):
                self.assertIn(label, texts, (game_id, label))
            self.assertNotIn(editor.layout.note, texts)
            self.assertFalse(hasattr(editor, 'show_mechanics'))

    def test_dw4_selected_field_guidance_preserves_ranges_and_max_rules(self):
        from tests.test_dw4hyper_format import procedural_raw
        from tests.test_dw4xl_format import procedural_psu
        self.root.deiconify()
        self.root.geometry('1080x820')
        for game_id, raw, special in (('dw4hyper', procedural_raw(), '36001'),
                                      ('dw4xl_ps2', procedural_psu(), '36002')):
            editor = self.app.select_game(game_id)
            editor.workspace_tabs.select(editor.edit_page)
            editor.document = editor.backend.decode(raw, game_id)
            editor.refresh()
            for key, expected in (('officer_0_attack', '255'),
                                  ('officer_0_weapon_experience', special),
                                  ('item_0', '1..20'),
                                  ('team_0_points', 'excluded from bulk Max'),
                                  ('difficulty', 'Difficulty is excluded from bulk Max')):
                with self.subTest(game=game_id, field=key):
                    editor.fields.selection_set(key)
                    editor.selected()
                    self.root.update()
                    self.assertIn(expected, editor.selection_info.get())
                    for phrase in REMOVED_UI_PHRASES:
                        self.assertNotIn(phrase.lower(), editor.selection_info.get().lower())
                    self.assertTrue(editor.selection_label.winfo_ismapped())
                    self.assertGreaterEqual(editor.selection_label.winfo_height(),
                                            editor.selection_label.winfo_reqheight())
                    self.assertLessEqual(editor.selection_label.winfo_rooty() + editor.selection_label.winfo_height(),
                                         self.root.winfo_rooty() + self.root.winfo_height())

    def test_dw3_cli_dispatch_normalizes_accepted_argument_order(self):
        from koei_editor.application import main
        args = ['application.py','--self-test','copy.sav','output','--game','dw3']
        observed = []
        with patch.object(sys, 'argv', args), patch.object(gui, 'main', side_effect=lambda: observed.extend(sys.argv)):
            main()
            self.assertIs(sys.argv, args)
        self.assertEqual(observed, ['application.py','--self-test','copy.sav','output'])

    def test_hidden_pc_edits_can_cancel_close_and_failed_open_preserves_edits(self):
        from tests.test_verified_editors import synthetic_raw
        import koei_editor.shared.verified_editor as backend
        import koei_editor.shared.verified_gui as verified_gui
        editor = self.app.select_game('pw3')
        editor.document = backend.decode(synthetic_raw('pw3'), 'pw3')
        editor.stage_values({'character_0_attack':123})
        self.app.show_library()
        with patch.object(verified_gui.messagebox, 'askyesno', return_value=False), \
                patch.object(self.root, 'destroy') as destroy:
            self.app.close()
            destroy.assert_not_called()
        with patch.object(verified_gui.filedialog, 'askopenfilename', return_value='wrong.bin'), \
                patch.object(verified_gui.messagebox, 'showerror') as error:
            editor.open()
            error.assert_called_once()
        self.assertEqual(editor.changes, {'character_0_attack':123})

    def test_dw3_synthetic_save_edit_undo_review_switch_and_save_as_workflow(self):
        from tests.test_elixirs_v11 import synthetic_reset_save
        from koei_editor.games.dw3.save_parser import read_save
        import koei_editor.games.dw3.progression_editor as progression_editor
        editor = self.app.select_game('dw3')
        document = synthetic_reset_save()
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'GameStatusData.sav'
            source.write_bytes(document.encrypted)
            errors = []
            with patch.object(gui.messagebox, 'showerror', side_effect=lambda *args: errors.append(args)), \
                    patch.object(gui.filedialog, 'askopenfilename', return_value=str(source)):
                editor.open()
                self.assertEqual(errors, [])
                self.assertEqual(editor.backup.read_bytes(), document.encrypted)
                editor.max_elixirs()
                self.assertTrue(editor.changes)
                editor.undo()
                self.assertFalse(editor.changes)
                editor.max_elixirs()
                editor.review()
                self.app.select_game('origins')
                self.app.apply_theme('Dark')
                self.assertIs(self.app.select_game('dw3'), editor)
                target = Path(folder) / 'edited.sav'
                editor.save_to(target)
                self.assertEqual(errors, [])
                self.assertEqual(progression_editor.elixir_state(read_save(target))['value'], 999)
                self.assertEqual(source.read_bytes(), document.encrypted)
                self.assertFalse(editor.changes)


if __name__ == '__main__':
    unittest.main()
