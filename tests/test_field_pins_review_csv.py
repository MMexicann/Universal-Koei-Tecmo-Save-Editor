"""Pinned navigation and complete, typed review exports on copied saves."""
import csv
from dataclasses import replace
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from koei_editor.games.origins.origins_game_editor import Editor
from koei_editor.shared import preferences
from koei_editor.shared.verified_gui import _review_csv
from tests.test_origins_parser import fixture


class PinPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.area = tempfile.TemporaryDirectory()
        self.addCleanup(self.area.cleanup)
        self.path = Path(self.area.name) / 'config' / 'preferences.json'

    def test_legacy_theme_migrates_only_on_pin_action_and_retains_exact_game_scope(self):
        self.assertTrue(preferences.save_theme('Dark', self.path))
        legacy = self.path.read_bytes()
        self.assertEqual(preferences.load_pins('dw7xl', self.path), ())
        self.assertEqual(self.path.read_bytes(), legacy)
        self.assertTrue(preferences.save_pins('dw7xl', ['gold', 'officer_12_attack'], self.path))
        self.assertTrue(preferences.save_pins('dw7xl_ps3', ['gold'], self.path))
        self.assertEqual(preferences.load_theme(self.path), 'Dark')
        self.assertEqual(preferences.load_pins('dw7xl', self.path), ('gold', 'officer_12_attack'))
        self.assertEqual(preferences.load_pins('dw7xl_ps3', self.path), ('gold',))
        self.assertEqual(preferences.load_pins('dw7', self.path), ())
        self.assertTrue(preferences.save_theme('Light', self.path))
        self.assertEqual(preferences.load_pins('dw7xl', self.path), ('gold', 'officer_12_attack'))
        content = json.loads(self.path.read_bytes())
        self.assertEqual(set(content), {'schema', 'theme', 'pins'})
        self.assertEqual(content['schema'], 2)
        self.assertTrue(preferences.save_pins('dw7xl', [], self.path))
        self.assertEqual(preferences.load_pins('dw7xl_ps3', self.path), ('gold',))
        self.assertTrue(preferences.save_pins('dw7xl_ps3', [], self.path))
        self.assertEqual(json.loads(self.path.read_bytes()), {'schema': 1, 'theme': 'Light'})

    def test_bounded_schema_rejects_values_paths_foreign_keys_and_corrupt_data_without_rewriting(self):
        valid = {'schema': 2, 'theme': 'Dark', 'pins': {'origins': ['gold']}}
        bad = [dict(valid, schema=True), dict(valid, theme='Other'), dict(valid, save='/private/save.dat'),
               dict(valid, pins={'origins': ['gold', 'gold']}), dict(valid, pins={'../dw7': ['gold']}),
               dict(valid, pins={'origins': ['save/copy.dat']}), dict(valid, pins={'origins': [True]}),
               dict(valid, pins={'origins': ['x' * 161]}),
               dict(valid, pins={'origins': ['x' + str(i) for i in range(preferences.MAX_PINNED_FIELDS + 1)]}),
               dict(valid, pins={'game_' + str(i): ['gold'] for i in range(preferences.MAX_PIN_GAMES + 1)})]
        self.path.parent.mkdir()
        for value in bad:
            raw = json.dumps(value).encode('utf-8')
            self.path.write_bytes(raw)
            self.assertEqual(preferences.load_theme(self.path), 'Light')
            self.assertEqual(preferences.load_pins('origins', self.path), ())
            self.assertEqual(self.path.read_bytes(), raw)
        for game, ids in (('../game', ['gold']), ('origins', ['/private/copy']),
                          ('origins', ['x'] * (preferences.MAX_PINNED_FIELDS + 1)),
                          ('origins', 'gold')):
            before = self.path.read_bytes()
            self.assertFalse(preferences.save_pins(game, ids, self.path))
            self.assertEqual(self.path.read_bytes(), before)

    def test_duplicate_json_properties_and_oversized_preferences_are_ignored_without_rewrite(self):
        self.path.parent.mkdir()
        variants = (b'{"schema":1,"theme":"Light","theme":"Dark"}',
                    b'{"schema":1,"schema":2,"theme":"Dark","pins":{}}',
                    b'{"schema":2,"theme":"Dark","pins":{"origins":["gold"],"origins":["skill_points"]}}',
                    b'{"schema":2,"theme":"Dark","pins":{},"extra":NaN}',
                    b'[' * 2000,
                    b'x' * (preferences.MAX_BYTES + 1))
        for raw in variants:
            with self.subTest(raw=raw[:80]):
                self.path.write_bytes(raw)
                self.assertEqual(preferences.load_theme(self.path), 'Light')
                self.assertEqual(preferences.load_pins('origins', self.path), ())
                self.assertEqual(self.path.read_bytes(), raw)

    def test_failed_pin_write_preserves_theme_other_games_and_completed_preferences(self):
        self.assertTrue(preferences.save_theme('Dark', self.path))
        self.assertTrue(preferences.save_pins('dw7xl', ['gold'], self.path))
        before = self.path.read_bytes()
        with patch.object(preferences.os, 'replace', side_effect=PermissionError('Read only')):
            self.assertFalse(preferences.save_pins('origins', ['gold'], self.path))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob('.preferences.*')), [])


class ReviewCsvEncodingTests(unittest.TestCase):
    def test_text_formula_labels_quoting_unicode_newlines_and_typed_values_roundtrip(self):
        records = []
        dangerous = ('=SUM(A1:A2)', '+formula', '-formula', '@formula', ' \t\r=1+1', '\x00=1+1', '\ufeff@formula',
                     '\u00a0=1+1', '\u200b@formula', '\x08+formula', '\u2028-formula')
        for index, label in enumerate(dangerous):
            before, after = ('=raw,"雪"\nsecond\tline', '-raw') if index % 2 else (-123, 9007199254740993)
            records.append(('dw7xl', '0' * 64, False, 'field_' + str(index),
                            '+group', '@record', label, type(before).__name__, before,
                            type(after).__name__, after))
        raw = _review_csv(records)
        self.assertTrue(raw.startswith(b'\xef\xbb\xbf'))
        rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline='')))
        self.assertEqual(len(rows), len(records))
        for row, original in zip(rows, records):
            self.assertEqual(row['label'], "'" + original[6])
            self.assertEqual(row['group'], "'+group")
            self.assertEqual(row['record'], "'@record")
            self.assertEqual(json.loads(row['opened_json']), original[8])
            self.assertIs(type(json.loads(row['opened_json'])), type(original[8]))
            self.assertEqual(json.loads(row['pending_json']), original[10])
            self.assertIs(type(json.loads(row['pending_json'])), type(original[10]))


class ReviewExportVerificationTests(unittest.TestCase):
    def setUp(self):
        from koei_editor.shared import verified_gui
        self.gui = verified_gui
        area = tempfile.TemporaryDirectory()
        self.addCleanup(area.cleanup)
        self.folder = Path(area.name).resolve()
        self.destination = self.folder / 'review.changes.json'
        self.data = b'{"game_id":"origins","changes":[]}\n'

    @staticmethod
    def changed_stat(info, **changes):
        names = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode', 'st_nlink')
        return SimpleNamespace(**{**{name: getattr(info, name) for name in names}, **changes})

    def test_valid_path_and_handle_ctime_semantics_may_differ(self):
        original = self.gui.os.fstat
        calls = []
        def handle_stat(descriptor):
            info = original(descriptor)
            calls.append(info)
            # Windows path stat uses legacy creation time, whereas CPython's
            # handle stat can expose the later native ChangeTime as ctime.
            return self.changed_stat(info, st_ctime_ns=info.st_ctime_ns + 123456789)
        with patch.object(self.gui.os, 'fstat', side_effect=handle_stat):
            output = self.gui._export_review(self.data, self.destination)
        self.assertGreaterEqual(len(calls), 2)
        self.assertEqual(output.read_bytes(), self.data)

    def test_handle_ctime_change_still_rejects_without_path_stat_change(self):
        original = self.gui.os.fstat
        calls = []
        def handle_stat(descriptor):
            info = original(descriptor)
            calls.append(info)
            return self.changed_stat(info, st_ctime_ns=info.st_ctime_ns + 123456789 + int(len(calls) > 1))
        with patch.object(self.gui.os, 'fstat', side_effect=handle_stat), self.assertRaisesRegex(ValueError, 'changed during read-back'):
            self.gui._export_review(self.data, self.destination)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.destination.read_bytes(), self.data)

    def test_path_ctime_change_still_rejects_without_handle_stat_change(self):
        original, close = Path.lstat, self.gui.os.close
        watched = (self.destination, self.destination.resolve())
        closed, changed = [], []
        def after_close(descriptor):
            close(descriptor)
            closed.append(True)
        def path_stat(path, *args, **kwargs):
            info = original(path, *args, **kwargs)
            if path in watched and closed:
                changed.append(True)
                return self.changed_stat(info, st_ctime_ns=info.st_ctime_ns + 1)
            return info
        with patch.object(Path, 'lstat', path_stat), patch.object(self.gui.os, 'close', side_effect=after_close), \
                self.assertRaisesRegex(ValueError, 'replaced during read-back'):
            self.gui._export_review(self.data, self.destination)
        self.assertEqual(len(closed), 1)
        self.assertTrue(changed)
        self.assertEqual(self.destination.read_bytes(), self.data)

    def test_common_handle_identity_still_binds_to_current_path(self):
        original = self.gui.os.fstat
        for attribute in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns'):
            with self.subTest(attribute=attribute):
                destination = self.folder / (attribute + '.changes.json')
                calls = []
                def changed(descriptor):
                    info = original(descriptor)
                    calls.append(True)
                    return self.changed_stat(info, **{attribute: getattr(info, attribute) + 1})
                with patch.object(self.gui.os, 'fstat', side_effect=changed), self.assertRaisesRegex(ValueError, 'changed before read-back'):
                    self.gui._export_review(self.data, destination)
                self.assertEqual(len(calls), 1)
                self.assertEqual(destination.read_bytes(), self.data)

    def test_same_bytes_symlink_replacement_before_baseline_is_rejected_and_retained(self):
        foreign = self.folder / 'foreign.changes.json'
        foreign.write_bytes(self.data)
        probe = self.folder / 'probe-link'
        try:
            probe.symlink_to(foreign)
        except (OSError, NotImplementedError):
            self.skipTest('This host cannot create symlinks')
        probe.unlink()
        atomic = self.gui.atomic_new
        retained = self.folder / 'created-report-retained.json'
        redirects = []
        def redirected(data, path):
            result = atomic(data, path)
            self.gui.os.replace(result, retained)
            result.symlink_to(foreign)
            redirects.append(result)
            return result
        with patch.object(self.gui, 'atomic_new', side_effect=redirected), self.assertRaisesRegex(ValueError, 'retained; do not use'):
            self.gui._export_review(self.data, self.destination)
        self.assertEqual(len(redirects), 1)
        self.assertTrue(self.destination.is_symlink())
        self.assertEqual(self.destination.resolve(), foreign)
        self.assertEqual(foreign.read_bytes(), self.data)
        self.assertEqual(retained.read_bytes(), self.data)

    def test_same_bytes_foreign_file_replacement_after_descriptor_close_is_retained(self):
        close = self.gui.os.close
        replacements = []
        def replace_after_close(descriptor):
            close(descriptor)
            if not replacements:
                replacement = self.folder / 'foreign.tmp'
                replacement.write_bytes(self.data)
                replacements.append(replacement.stat().st_ino)
                self.gui.os.replace(replacement, self.destination)
        with patch.object(self.gui.os, 'close', side_effect=replace_after_close), self.assertRaisesRegex(ValueError, 'replaced during read-back'):
            self.gui._export_review(self.data, self.destination)
        self.assertEqual(len(replacements), 1)
        self.assertEqual(self.destination.stat().st_ino, replacements[0])
        self.assertEqual(self.destination.read_bytes(), self.data)


class PinnedReviewGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(self.root.destroy)
        self.area = tempfile.TemporaryDirectory()
        self.addCleanup(self.area.cleanup)
        self.folder = Path(self.area.name)
        self.prefs = self.folder / 'prefs.json'
        self.source = self.folder / 'SLOT0000.dat'
        self.raw = fixture()
        self.source.write_bytes(self.raw)
        self.editor = Editor(self.root)
        self.root.geometry('1080x820')
        with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(self.source)):
            self.editor.open()
        self.root.update()

    def review(self):
        self.editor.review()
        return next(child for child in self.root.winfo_children()
                    if isinstance(child, tk.Toplevel) and child.title() == 'Review Changes')

    @staticmethod
    def button(dialog, label):
        return next(child for child in dialog.winfo_children()
                    if isinstance(child, ttk.Button) and child.cget('text') == label)

    def test_real_pins_filters_staging_undo_restart_and_unavailable_dynamic_ids(self):
        editor = self.editor
        editor.configure_pins(['unavailable_record_field'],
                              lambda ids: preferences.save_pins('origins', ids, self.prefs))
        editor.stage_values({'gold': 1234})
        history = [dict(item) for item in editor.history]
        editor.fields.selection_set(('gold', 'skill_points'))
        editor.pin_selected()
        self.assertEqual(editor.pinned_fields, frozenset(('gold', 'skill_points', 'unavailable_record_field')))
        self.assertEqual(editor.changes, {'gold': 1234})
        self.assertEqual(editor.history, history)
        self.assertIn('* ', editor.fields.item('gold', 'values')[1])
        self.assertEqual(editor.pin_count.get(), 'Pinned only (2)')
        editor.pinned_only.set(True)
        editor.refresh()
        self.assertEqual(set(editor.fields.get_children()), {'gold', 'skill_points'})
        editor.pending_only.set(True)
        editor.search.set('gold')
        self.assertEqual(editor.fields.get_children(), ('gold',))
        editor.clear_field_filters()
        self.assertFalse(editor.pinned_only.get())
        self.assertEqual(editor.changes, {'gold': 1234})
        self.assertEqual(editor.history, history)
        editor.undo()
        self.assertEqual(editor.changes, {})
        self.assertEqual(self.source.read_bytes(), self.raw)
        pins = preferences.load_pins('origins', self.prefs)
        self.assertEqual(set(pins), {'gold', 'skill_points', 'unavailable_record_field'})
        editor.configure_pins(pins)
        editor.pinned_only.set(True)
        editor.refresh()
        editor.fields.selection_set('gold')
        editor.unpin_selected()
        self.assertEqual(editor.fields.get_children(), ('skill_points',))
        self.assertIn('unavailable_record_field', editor.pinned_fields)
        self.assertEqual(editor.changes, {})

    def test_preferences_failure_keeps_navigation_usable_and_does_not_change_pending(self):
        editor = self.editor
        editor.configure_pins((), lambda ids: False)
        editor.stage_values({'gold': 5})
        history = [dict(item) for item in editor.history]
        editor.fields.selection_set('gold')
        editor.pin_selected()
        self.assertEqual(editor.pinned_fields, frozenset(('gold',)))
        self.assertIn('for this session', editor.status.get())
        self.assertEqual(editor.changes, {'gold': 5})
        self.assertEqual(editor.history, history)
        editor.pinned_only.set(True)
        editor.refresh()
        self.assertEqual(editor.fields.get_children(), ('gold',))
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_csv_exports_complete_frozen_review_when_filtered_and_source_document_changes(self):
        editor = self.editor
        editor.stage_values({'gold': 1234, 'skill_points': 88})
        original_hash = editor.document.sha256
        dialog = self.review()
        dialog.review_query.set('gold')
        self.assertEqual(len(dialog.review_tree.get_children()), 1)
        editor.stage_values({'gold': 999})
        other = self.folder / 'SLOT0001.dat'
        other.write_bytes(self.raw)
        editor.document = replace(editor.document, source=other)
        chosen, destination = self.folder / 'APP.BIN', self.folder / 'APP.BIN.changes.csv'
        chosen.write_bytes(b'Never replace the selected save or any existing file.')
        with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(chosen)) as choose, \
             patch('koei_editor.shared.verified_gui.messagebox.showerror') as error:
            self.button(dialog, 'Export CSV...').invoke()
        error.assert_not_called()
        rows = list(csv.DictReader(io.StringIO(destination.read_text(encoding='utf-8-sig'), newline='')))
        self.assertEqual({row['field_id']: json.loads(row['pending_json']) for row in rows},
                         {'gold': 1234, 'skill_points': 88})
        self.assertEqual({row['source_sha256'] for row in rows}, {original_hash})
        self.assertEqual({row['game_id'] for row in rows}, {'origins'})
        self.assertEqual({row['pending_type'] for row in rows}, {'int'})
        self.assertEqual(choose.call_args.kwargs['initialfile'], 'SLOT0000.changes.csv')
        self.assertFalse(choose.call_args.kwargs['confirmoverwrite'])
        self.assertEqual(chosen.read_bytes(), b'Never replace the selected save or any existing file.')
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertEqual(editor.changes, {'gold': 999, 'skill_points': 88})
        with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(chosen)), \
             patch('koei_editor.shared.verified_gui.messagebox.showerror') as error:
            self.button(dialog, 'Export CSV...').invoke()
        error.assert_called_once()
        self.assertIn('existing files are never replaced', error.call_args.args[1])
        self.assertEqual(len(list(csv.DictReader(io.StringIO(destination.read_text(encoding='utf-8-sig'))))), 2)

    def test_csv_cancel_and_normalized_names_preserve_files_and_pending(self):
        self.editor.stage_values({'gold': 1234})
        dialog = self.review()
        self.root.update()
        for label in ('Export Review...', 'Export CSV...', 'Copy Selected', 'Close'):
            button = self.button(dialog, label)
            self.assertTrue(button.winfo_ismapped())
            self.assertLessEqual(button.winfo_rooty() + button.winfo_height(),
                                 dialog.winfo_rooty() + dialog.winfo_height())
        export = self.button(dialog, 'Export CSV...')
        before = {p: p.read_bytes() for p in self.folder.rglob('*') if p.is_file()}
        with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=''):
            export.invoke()
        self.assertEqual({p: p.read_bytes() for p in self.folder.rglob('*') if p.is_file()}, before)
        for selected, expected in (('plain', 'plain.changes.csv'), ('report.csv', 'report.changes.csv'),
                                   ('partial.changes', 'partial.changes.csv'),
                                   ('ready.CHANGES.CSV', 'ready.CHANGES.CSV'),
                                   ('雪 report', '雪 report.changes.csv')):
            with self.subTest(selected=selected), \
                 patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename',
                       return_value=str(self.folder / selected)), \
                 patch('koei_editor.shared.verified_gui.messagebox.showerror') as error:
                export.invoke()
                error.assert_not_called()
                self.assertTrue((self.folder / expected).is_file())
        self.assertEqual(self.editor.changes, {'gold': 1234})
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_review_hash_is_computed_once_and_remains_frozen_for_later_exports(self):
        editor = self.editor
        editor.stage_values({'gold': 1234, 'skill_points': 88})
        document = editor.document
        native_property = type(document).sha256
        original_hash = document.sha256
        calls = []
        def counted(snapshot):
            calls.append(snapshot)
            return native_property.fget(snapshot)
        with patch.object(type(document), 'sha256', property(counted)):
            dialog = self.review()
            self.assertEqual(len(calls), 1, 'Review must not hash a complete save once per field')
            other = self.folder / 'SLOT0001.dat'
            other.write_bytes(fixture(gold=3500))
            editor.document = editor.adapter.read_save(other)
            destination = self.folder / 'frozen-hash.changes.json'
            with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(destination)):
                self.button(dialog, 'Export Review...').invoke()
            self.assertEqual(len(calls), 1)
        report = json.loads(destination.read_bytes())
        self.assertEqual(report['source_sha256'], original_hash)
        self.assertEqual({row['field']: row['after'] for row in report['changes']}, {'gold': 1234, 'skill_points': 88})

    def test_review_report_replacement_is_retained_and_never_reported_as_success(self):
        from koei_editor.shared import verified_gui
        self.editor.stage_values({'gold': 1234, 'skill_points': 88})
        original = (dict(self.editor.changes), [dict(item) for item in self.editor.history])
        dialog = self.review()
        atomic = verified_gui.atomic_new
        for button, suffix in (('Export Review...', '.changes.json'), ('Export CSV...', '.changes.csv')):
            with self.subTest(format=suffix):
                chosen = self.folder / ('replaced' + suffix)
                foreign = b'Concurrent foreign report replacement'
                def replaced(data, path):
                    result = atomic(data, path)
                    result.write_bytes(foreign)
                    return result
                with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(chosen)), \
                     patch.object(verified_gui, 'atomic_new', side_effect=replaced), \
                     patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                    self.button(dialog, button).invoke()
                errors.assert_called_once()
                self.assertIn('retained; do not use', str(errors.call_args))
                self.assertEqual(chosen.read_bytes(), foreign)
                self.assertNotIn('exported:', self.editor.status.get())
        self.assertEqual((self.editor.changes, self.editor.history), original)
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_replacement_during_report_readback_is_detected_without_deleting_foreign_bytes(self):
        from koei_editor.shared import verified_gui
        self.editor.stage_values({'gold': 1234})
        dialog = self.review()
        chosen = self.folder / 'read-race.changes.csv'
        read = verified_gui.os.read
        mutations = []
        foreign = b'A different process owns this report now.'
        def replaced(descriptor, count):
            result = read(descriptor, count)
            if not mutations:
                chosen.write_bytes(foreign)
                mutations.append(True)
            return result
        with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(chosen)), \
             patch.object(verified_gui.os, 'read', side_effect=replaced), \
             patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            self.button(dialog, 'Export CSV...').invoke()
        self.assertEqual(len(mutations), 1)
        errors.assert_called_once()
        self.assertEqual(chosen.read_bytes(), foreign)
        self.assertEqual(self.editor.changes, {'gold': 1234})
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_new_action_bar_buttons_and_pin_controls_fit_minimum_window(self):
        self.root.update()
        required = ('Save As...', 'Backup Save', 'Review Changes', 'Undo', 'Edit Presets...')
        buttons = {button.cget('text'): button for button in self.editor.save_buttons}
        for label in required:
            button = buttons[label]
            self.assertTrue(button.winfo_ismapped())
            self.assertEqual(str(button['state']), 'normal')
            self.assertGreaterEqual(button.winfo_rootx(), self.root.winfo_rootx())
            self.assertLessEqual(button.winfo_rootx() + button.winfo_width(), self.root.winfo_rootx() + self.root.winfo_width())
        original = (dict(self.editor.changes), list(self.editor.history))
        with patch('koei_editor.shared.preset_gui.open_presets', return_value=None) as opened:
            buttons['Edit Presets...'].invoke()
        opened.assert_called_once_with(self.editor)
        self.assertEqual((self.editor.changes, self.editor.history), original)
        self.editor.workspace_tabs.select(self.editor.edit_page)
        self.root.update()
        self.assertGreater(self.editor.fields.winfo_height(), 220)

    def test_copy_selected_uses_filtered_frozen_display_without_staging(self):
        self.editor.stage_values({'gold': 1234, 'skill_points': 88})
        history = [dict(item) for item in self.editor.history]
        dialog = self.review()
        dialog.review_query.set('gold')
        dialog.review_tree.selection_set(dialog.review_tree.get_children())
        self.editor.stage_values({'gold': 999})
        self.button(dialog, 'Copy Selected').invoke()
        self.root.update()
        copied = self.root.clipboard_get()
        self.assertIn('Field / record\tOpened value\tPending value', copied)
        self.assertIn('Gold\t3,456\t1,234', copied)
        self.assertNotIn('Skill Points', copied)
        self.assertEqual(self.editor.changes, {'gold': 999, 'skill_points': 88})
        self.assertEqual(self.editor.history[:-1], history)
        self.assertEqual(self.source.read_bytes(), self.raw)


if __name__ == '__main__':
    unittest.main()
