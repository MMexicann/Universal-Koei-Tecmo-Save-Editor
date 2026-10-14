"""Opt-in limits preserve native validation, session isolation and copy safety."""
from dataclasses import replace
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.experimental_limits import (
    experimental_enabled, experimental_limits, within_numeric_limits)
from tests.test_verified_editors import synthetic_raw


class ExperimentalPolicyTests(unittest.TestCase):
    def test_scope_resets_after_nested_scopes_and_errors(self):
        self.assertFalse(experimental_enabled())
        with self.assertRaises(RuntimeError), experimental_limits(True):
            self.assertTrue(experimental_enabled())
            with experimental_limits(False):
                self.assertFalse(experimental_enabled())
            self.assertTrue(experimental_enabled())
            raise RuntimeError('scope ends')
        self.assertFalse(experimental_enabled())
        for mode in (1, 'yes', None):
            with self.assertRaises(SaveError):
                with experimental_limits(mode):
                    pass

    def test_optout_width_minimum_and_exact_integer_types(self):
        for mode in (False, True):
            with experimental_limits(mode):
                for value in (True, 1.0, '1', -1, 256):
                    self.assertFalse(within_numeric_limits(value, 0, 100, storage_maximum=255))
                self.assertTrue(within_numeric_limits(100, 0, 100, storage_maximum=255))
                self.assertEqual(within_numeric_limits(255, 0, 100, storage_maximum=255), mode)
                self.assertFalse(within_numeric_limits(101, 0, 100, storage_maximum=None))

    def test_bound_mode_survives_all_readback_and_new_copy_paths(self):
        normal = get_game('dw8xl').get_scalar_adapter()
        experimental = get_game('dw8xl').get_scalar_adapter(experimental=True)
        raw = synthetic_raw('dw8xl')
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = folder / 'input.dat'
            source.write_bytes(raw)
            doc = experimental.read_save(source)
            with experimental_limits(True), self.assertRaises(SaveError):
                normal.stage(doc, {}, 'gold', 10_000_000)
            pending = experimental.stage(doc, {}, 'gold', (1 << 32) - 1)
            serialized = experimental.serialize(doc, pending)
            self.assertEqual(experimental.field_map(experimental.decode(serialized))['gold'].value(
                experimental.decode(serialized).payload), (1 << 32) - 1)
            saved = experimental.save_as(doc, pending, folder / 'edited.dat')
            self.assertEqual(experimental.field_map(saved)['gold'].value(saved.payload), (1 << 32) - 1)
            self.assertEqual(source.read_bytes(), raw)
            self.assertEqual(normal.serialize(normal.read_save(saved.source), {}), serialized)
            self.assertEqual(experimental.stage(doc, pending, 'gold', 50), {})
            for value in ((1 << 32), True, '10000000'):
                with self.assertRaises(SaveError):
                    experimental.stage(doc, {}, 'gold', value)
        self.assertFalse(experimental_enabled())

    def test_max_and_choices_stay_supported_with_experimental_pending(self):
        adapter = get_game('dw8xl').get_scalar_adapter(experimental=True)
        document = adapter.decode(synthetic_raw('dw8xl'))
        pending = adapter.stage(document, {}, 'gold', 20_000_000)
        targets = adapter.limit_values(document, pending, ['gold', 'gems'])
        self.assertEqual(targets, {'gems': 9_999})
        self.assertEqual(pending, {'gold': 20_000_000})
        maxima = adapter.maximums(document, pending)
        for key, value in maxima.items():
            if value != pending.get(key):
                self.assertLessEqual(value, adapter.field_map(document)[key].maximum)
        for value in (101, 255):
            with self.assertRaises(SaveError):
                adapter.stage(document, pending, 'officer_0_compatibility_0', value)


class ExperimentalSharedGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        source = self.folder / 'input.dat'
        source.write_bytes(synthetic_raw('dw8xl'))
        self.editor = get_game('dw8xl').create_editor(self.root, self.root)
        with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)), \
                patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            self.editor.open()
        errors.assert_not_called()

    def enable(self, accepted=True):
        self.editor.experimental_mode.set(True)
        with patch('koei_editor.shared.verified_gui.messagebox.askyesno', return_value=accepted) as warning:
            self.editor.toggle_experimental()
        warning.assert_called_once()

    def test_enable_warning_cancel_limits_and_undo_history_gate(self):
        self.enable(False)
        self.assertFalse(self.editor.adapter.experimental)
        self.enable()
        self.assertTrue(self.editor.adapter.experimental)
        self.editor.stage_values({'gold': 20_000_000})
        self.assertIn('1 pending edits above', self.editor.limit_status.get())
        self.assertEqual(self.editor.fields.item('gold', 'values')[-1], '4,294,967,295')
        self.editor.fields.selection_set('gold')
        self.editor.revert_selected()
        self.editor.experimental_mode.set(False)
        self.editor.toggle_experimental()
        previous_history = list(self.editor.history)
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as error:
            self.editor.undo()
        error.assert_called_once()
        self.assertEqual(self.editor.changes, {})
        self.assertEqual(self.editor.history, previous_history)
        self.enable()
        self.editor.undo()
        self.assertEqual(self.editor.changes, {'gold': 20_000_000})

    def test_disable_and_save_cancellation_preserve_pending_then_native_save(self):
        self.enable()
        self.editor.stage_values({'gold': 20_000_000})
        self.editor.experimental_mode.set(False)
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as error:
            self.editor.toggle_experimental()
        error.assert_called_once()
        self.assertTrue(self.editor.experimental_mode.get())
        destination = self.folder / 'edited.dat'
        with patch('koei_editor.shared.verified_gui.messagebox.askyesno', return_value=False):
            self.editor.save_to(destination)
        self.assertFalse(destination.exists())
        self.assertEqual(self.editor.changes, {'gold': 20_000_000})
        with patch('koei_editor.shared.verified_gui.messagebox.askyesno', return_value=True), \
                patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            self.editor.save_to(destination)
        errors.assert_not_called()
        self.assertEqual(self.editor.adapter.field_map(self.editor.document)['gold'].value(
            self.editor.document.payload), 20_000_000)
        self.assertEqual(self.editor.changes, {})

    def test_new_open_resets_mode_after_dirty_confirmation(self):
        self.enable()
        source = self.folder / 'other.dat'
        source.write_bytes(synthetic_raw('dw8xl'))
        with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
            self.editor.open()
        self.assertFalse(self.editor.experimental_mode.get())
        self.assertFalse(self.editor.adapter.experimental)


if __name__ == '__main__':
    unittest.main()
