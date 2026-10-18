"""Native-unit editing actions reuse qualified scalars; never simulate rewards."""
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.origins import origins_parser as backend
from koei_editor.games.origins.origins_game_editor import Editor
from koei_editor.games.origins.origins_presentation import OriginsPresentation
from tests.test_origins_integration import mapped_fixture, LAYOUTS


class OriginsNativeActionTests(unittest.TestCase):
    def setUp(self):
        self.adapter = get_game('origins').get_scalar_adapter()

    def test_exact_percentage_and_training_actions_preserve_all_other_bytes(self):
        for revision, (bonds, peace, _weapons) in LAYOUTS.items():
            with self.subTest(revision=revision):
                document = self.adapter.decode(mapped_fixture(revision))
                pending = {'gold': 12345, 'bond_7_level': 4}
                values = backend.peace_percent_values(document, pending, ('peace_0', 'peace_8'), '12.34')
                values.update(backend.bond_training_values(document, pending, ('bond_7_training',)))
                for key, value in values.items():
                    pending = self.adapter.stage(document, pending, key, value)
                edited = self.adapter.decode(self.adapter.serialize(document, pending))
                expected = bytearray(document.payload)
                expected[0x69b:0x69f] = (12345).to_bytes(4, 'little')
                expected[bonds + 35] = 4
                expected[bonds + 37:bonds + 39] = (3).to_bytes(2, 'little')
                for offset in (peace, peace + 16):
                    expected[offset:offset + 2] = (1234).to_bytes(2, 'little')
                self.assertEqual(edited.payload, bytes(expected))
                self.assertEqual(edited.seed, document.seed)
                self.assertEqual(self.adapter.serialize(document, {}), document.raw)
                self.assertEqual(backend.bond_training_values(edited, {}, ('bond_7_training',)),
                                 {'bond_7_training': 3})
                self.assertEqual(self.adapter.stage(edited, {}, 'bond_7_training', 3), {})

    def test_percentage_precision_boundaries_and_unstage(self):
        document = self.adapter.decode(mapped_fixture(29))
        for percent, expected in (('0', 0), ('0.01', 1), ('99.99', 9999), ('100', 10000),
                                  ('100.00', 10000), (' 4.00 ', 400)):
            with self.subTest(percent=percent):
                self.assertEqual(backend.peace_percent_values(document, {}, ('peace_0',), percent),
                                 {'peace_0': expected})
        pending = self.adapter.stage(document, {}, 'peace_0', 9999)
        values = backend.peace_percent_values(document, pending, ('peace_0',), '4')
        self.assertEqual(self.adapter.stage(document, pending, 'peace_0', values['peace_0']), {})
        for percent in ('-1', '100.01', '1.001', 'NaN', 'Infinity', '1e2', '', '4%', True, 1.5):
            with self.subTest(percent=percent), self.assertRaises(SaveError):
                backend.peace_percent_values(document, {}, ('peace_0',), percent)

    def test_actions_reject_mixed_missing_or_unqualified_selection_and_invalid_pending(self):
        document = self.adapter.decode(mapped_fixture(29))
        for keys in ((), ('peace_0', 'gold'), ('peace_2',), ('peace_13',), (True,)):
            with self.subTest(keys=keys), self.assertRaises(SaveError):
                backend.peace_percent_values(document, {}, keys, '10')
        for keys in ((), ('bond_7_training', 'bond_7_level'), ('bond_9_training',),
                     ('bond_0_training',), ('bond_10_training',), (True,)):
            with self.subTest(keys=keys), self.assertRaises(SaveError):
                backend.bond_training_values(document, {}, keys)
        for pending in ({'gold': True}, {'proficiency_0': 123}, {'bond_7_training': -1}):
            with self.subTest(pending=pending):
                with self.assertRaises(SaveError):
                    backend.peace_percent_values(document, pending, ('peace_0',), '10')
                with self.assertRaises(SaveError):
                    backend.bond_training_values(document, pending, ('bond_7_training',))
        for count in (3, 4, 999):
            self.assertEqual(backend.bond_training_values(document, {'bond_7_training': count},
                                                         ('bond_7_training',)),
                             {'bond_7_training': count})

    def test_training_action_does_not_reduce_higher_opened_count_or_pending_count(self):
        document = self.adapter.decode(mapped_fixture(29))
        document = self.adapter.decode(self.adapter.serialize(document, {'bond_7_training': 10}))
        pending = self.adapter.stage(document, {}, 'bond_7_training', 1)
        values = backend.bond_training_values(document, pending, ('bond_7_training',))
        self.assertEqual(values, {'bond_7_training': 10})
        self.assertEqual(self.adapter.stage(document, pending, 'bond_7_training', values['bond_7_training']), {})
        self.assertEqual(backend.bond_training_values(document, {'bond_7_training': 30},
                                                    ('bond_7_training',)),
                         {'bond_7_training': 30})

    def test_choices_enforce_saved_monotonic_history_and_native_bond_range(self):
        document = self.adapter.decode(mapped_fixture(29))
        self.assertEqual(tuple(value for value, _ in backend.field_options(document, 'bond_7_level')),
                         (1, 2, 3, 4, 5))
        self.assertEqual(tuple(value for value, _ in backend.field_options(document, 'battle_history_0')), (1,))
        self.assertEqual(tuple(value for value, _ in backend.field_options(document, 'battle_history_68')), (0, 1))
        reopened = self.adapter.decode(self.adapter.serialize(document, {'battle_history_68': 1}))
        self.assertEqual(tuple(value for value, _ in backend.field_options(reopened, 'battle_history_68')), (1,))
        self.assertEqual(backend.field_options(document, 'bond_7_training'), ())
        from koei_editor.shared.experimental_limits import experimental_limits
        with experimental_limits():
            # Preserve the existing explicit experimental numeric entry path.
            self.assertEqual(backend.field_options(document, 'bond_7_level'), ())
        with self.assertRaises(SaveError):
            backend.field_options(document, 'battle_history_70')

    def test_weapon_inspector_reports_existing_instance_bytes_without_enabling_writes(self):
        document = self.adapter.decode(mapped_fixture(29))
        table = OriginsPresentation(backend, 'origins').inspection_tables(document)[0]
        row = next(row for row in table.rows if row[0] == 44)
        self.assertEqual(row[6:], (0xa7a7a7a7, 'A7 A7', 'Qualified existing reforgable weapon'))
        special = next(row for row in table.rows if row[0] == 48)
        self.assertIn('material flag excludes', special[-1])
        unusual = next(row for row in table.rows if row[0] == 46)
        self.assertIn('exceeds supported range', unusual[-1])
        self.assertIn('stored instance ID', backend.field_hint(document, 'weapon_0043_upgrade'))
        with self.assertRaises(SaveError):
            self.adapter.stage(document, {}, 'weapon_0043_instance_id', 1)


class OriginsNativeActionGuiTests(unittest.TestCase):
    def test_actions_stage_once_undo_save_and_preserve_source(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        root.withdraw()
        self.addCleanup(root.destroy)
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'slot-copy.dat'
            original = mapped_fixture(29)
            source.write_bytes(original)
            editor = Editor(root)
            with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                self.assertTrue(editor.open_path(source))
                self.assertEqual(str(editor.peace_button['state']), 'disabled')
                editor.fields.selection_set(('peace_0', 'peace_8'))
                editor.selected()
                self.assertEqual(str(editor.peace_button['state']), 'normal')
                self.assertEqual(str(editor.training_button['state']), 'disabled')
                with patch('koei_editor.games.origins.origins_game_editor.simpledialog.askstring',
                           return_value='12.34'):
                    editor.set_peace_percent()
                self.assertEqual(editor.changes, {'peace_0': 1234, 'peace_8': 1234})
                self.assertEqual(len(editor.history), 1)
                editor.undo()
                self.assertEqual(editor.changes, {})
                editor.fields.selection_set('bond_7_training')
                editor.selected()
                self.assertEqual(str(editor.training_button['state']), 'normal')
                editor.meet_training_count()
                self.assertEqual(editor.changes, {'bond_7_training': 3})
                editor.meet_training_count()
                self.assertEqual(len(editor.history), 1)
                target = Path(folder) / 'edited.dat'
                reopened = editor.adapter.save_as(editor.document, editor.changes, target)
                self.assertEqual(editor.adapter.field_map(reopened)['bond_7_training'].value(reopened.payload), 3)
                self.assertEqual(source.read_bytes(), original)
                self.assertTrue(editor.backup.exists())
                errors.assert_not_called()


if __name__ == '__main__':
    unittest.main()
