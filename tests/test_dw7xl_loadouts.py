"""Native equipment dependencies; procedural saves are not game-load proof."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw7xl import dw7xl_codec as codec
from koei_editor.games.dw7xl import dw7xl_parser as backend
from koei_editor.games.dw7xl import equipment
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from tests.test_dw7xl_format import synthetic_raw


def loadout_document():
    original = backend.decode(synthetic_raw())
    payload = bytearray(original.payload)
    payload[equipment.SUSPEND_FLAG] = 0
    payload[equipment.SMITH_REFERENCES:equipment.SMITH_REFERENCES + 10] = b'\xff' * 10
    payload[equipment.SEAL_MASK:equipment.SEAL_MASK + 12] = b'\x8b\0' + b'\0' * 10
    for index in range(backend.WEAPON_COUNT):
        start = backend.WEAPON_BASE + index * backend.WEAPON_STRIDE
        payload[start + 4:start + 6] = b'\0\0'
        payload[start + 8:start + 18] = b'\xff' * 10
    for identity in (2, 4, 9, 13):
        start = backend.WEAPON_BASE + identity * backend.WEAPON_STRIDE
        payload[start + 4:start + 6] = b'\x15\0'
    for index in range(backend.OFFICER_COUNT):
        start = backend.OFFICER_BASE + index * backend.OFFICER_STRIDE
        payload[start + 18:start + 24] = b'\x02\0\x04\0\0\0'
    payload[backend.OFFICER_BASE + backend.OFFICER_STRIDE + 18:
            backend.OFFICER_BASE + backend.OFFICER_STRIDE + 20] = b'\x09\0'
    start = backend.WEAPON_BASE + 2 * backend.WEAPON_STRIDE
    payload[start + 8:start + 12] = b'\0\0\x01\0'
    return backend.decode(codec.encode(payload, original.seed))


class DW7LoadoutTests(unittest.TestCase):
    def setUp(self):
        self.document = loadout_document()
        self.adapter = BoundScalarAdapter('dw7xl', '.dat', backend)

    def mutate(self, offset, data):
        payload = bytearray(self.document.payload)
        payload[offset:offset + len(data)] = data
        return backend.decode(codec.encode(payload, self.document.seed))

    def assert_surgical(self, document, changes):
        result = backend.decode(backend.serialize(document, changes))
        expected = bytearray(document.payload)
        for key, value in changes.items():
            field = backend.field_map(document)[key]
            expected[field.offset:field.offset + field.size] = value.to_bytes(field.size, 'little')
        self.assertEqual(result.payload, expected)
        self.assertEqual(result.seed, document.seed)
        self.assertEqual(backend.serialize(document, {}), document.raw)
        return result

    def test_source_witnessed_weapon_choices_preserve_parameters_and_full_copy(self):
        key = 'officer_0_weapon_1'
        self.assertEqual(equipment.weapon_choices(self.document.payload), (2, 4, 9))
        self.assertEqual([value for value, _ in backend.field_options(self.document, key)], [2, 9])
        pending = self.adapter.stage(self.document, {}, key, 9)
        self.assert_surgical(self.document, pending)
        self.assertEqual(self.adapter.stage(self.document, pending, key, 2), {})
        self.assertEqual(len(self.adapter.review(self.document, pending)), 1)
        for value in (True, -1, 4, 11, 13, backend.WEAPON_COUNT, 65535):
            with self.subTest(value=value), self.assertRaises(SaveError):
                self.adapter.stage(self.document, {}, key, value)

    def test_final_pair_dependencies_and_valid_atomic_swap(self):
        with self.assertRaisesRegex(SaveError, 'same physical weapon'):
            backend.serialize(self.document, {'officer_0_weapon_1': 4})
        self.assert_surgical(self.document, {'officer_0_weapon_1': 4, 'officer_0_weapon_2': 2})
        with self.assertRaises(SaveError):
            self.adapter.stage(self.document, {'officer_0_weapon_1': 13}, 'gold', 1)

    def test_smith_reserved_and_suspended_equipment_are_not_exposed(self):
        reserved = self.mutate(equipment.SMITH_REFERENCES, b'\x09\0')
        self.assertNotIn(9, equipment.weapon_choices(reserved.payload))
        with self.assertRaises(SaveError):
            backend.serialize(reserved, {'officer_0_weapon_1': 9})
        for value in (1, 2, 255):
            document = self.mutate(equipment.SUSPEND_FLAG, bytes([value]))
            self.assertFalse(any(equipment.reference_key(field.id) or equipment.seal_key(field.id)
                                 for field in backend.fields_for(document)))
            self.assertEqual(backend.serialize(document, {}), document.raw)
            # A new equipment dependency does not suppress unrelated established fields.
            self.assert_surgical(document, {'gold': 17})

    def test_learned_seal_substitution_removal_and_reopening(self):
        key = 'weapon_2_applied_seal_1'
        self.assertEqual([value for value, _ in backend.field_options(self.document, key)],
                         [65535, 0, 3, 7])
        for value in (3, 7, 65535):
            pending = self.adapter.stage(self.document, {}, key, value)
            result = self.assert_surgical(self.document, pending)
            self.assertEqual(self.adapter.stage(self.document, pending, key, 0), {})
            if value == 65535:
                self.assertNotIn(key, backend.field_map(result))
                self.assertIn('weapon_2_applied_seal_2', backend.field_map(result))
        self.assertNotIn('weapon_2_applied_seal_3', backend.field_map(self.document))
        for value in (True, -1, 1, 2, 63, 64, 91, 65534, 65536):
            with self.subTest(value=value), self.assertRaises(SaveError):
                backend.serialize(self.document, {key: value})

    def test_final_seal_map_checks_duplicates_and_allows_atomic_exchange(self):
        self.assert_surgical(self.document, {'weapon_2_applied_seal_1': 1,
                                             'weapon_2_applied_seal_2': 0})
        with self.assertRaises(SaveError):
            self.adapter.stage(self.document, {'weapon_2_applied_seal_1': 2}, 'gold', 1)

    def test_unknown_unowned_unlearned_and_duplicate_records_remain_opaque(self):
        start = backend.WEAPON_BASE + 2 * backend.WEAPON_STRIDE
        variants = ((start + 4, b'\x14\0'), (start + 4, b'\x15\x80'),
                    (start + 10, b'\0\0'), (start + 10, b'\x40\0'),
                    (start + 10, b'\x02\0'), (equipment.SMITH_REFERENCES, b'\x02\0'))
        for offset, data in variants:
            document = self.mutate(offset, data)
            with self.subTest(offset=offset, data=data):
                self.assertNotIn('weapon_2_applied_seal_1', backend.field_map(document))
                self.assert_surgical(document, {'gold': 18})

    def test_choices_do_not_participate_in_max_or_experimental_storage_bypass(self):
        for group in ('Weapon loadouts', 'Applied seals'):
            self.assertEqual(backend.maximums(self.document, {}, group), {})
        adapter = BoundScalarAdapter('dw7xl', '.dat', backend, experimental=True)
        for key, value in (('officer_0_weapon_1', 13), ('weapon_2_applied_seal_1', 65000),
                           ('officer_0_attack', 32768)):
            with self.subTest(key=key), self.assertRaises(SaveError):
                adapter.stage(self.document, {}, key, value)
        pending = adapter.stage(self.document, {}, 'officer_0_attack', 32767)
        # Verify the actual experimental write through the bound adapter's context.
        result = adapter.decode(adapter.serialize(self.document, pending))
        self.assertEqual(backend.FIELD_MAP['officer_0_attack'].value(result.payload), 32767)

    def test_exact_unusual_opened_weapon_can_be_unstaged_and_preserved(self):
        document = self.mutate(backend.OFFICER_BASE + 20, b'\xff\xff')
        key = 'officer_0_weapon_2'
        pending = self.adapter.stage(document, {}, key, 9)
        self.assertEqual(self.adapter.stage(document, pending, key, 65535), {})
        self.assertEqual(backend.serialize(document, {key: 65535}), document.raw)

    def test_save_as_backup_restore_preserve_source_and_dependencies(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'input.dat'
            source.write_bytes(self.document.raw)
            document = self.adapter.read_save(source)
            pending = self.adapter.stage(document, {}, 'officer_0_weapon_1', 9)
            pending = self.adapter.stage(document, pending, 'weapon_2_applied_seal_1', 3)
            output = self.adapter.save_as(document, pending, root / 'output.dat')
            self.assertEqual(output.payload, backend.changed_payload(document, pending))
            self.assertEqual(source.read_bytes(), self.document.raw)
            snapshot = self.adapter.backup(document)
            restored = self.adapter.restore(snapshot, root / 'restored.dat')
            self.assertEqual(restored.read_bytes(), self.document.raw)

    def test_actual_gui_choices_search_review_undo_and_saved_copy(self):
        import tkinter as tk
        from koei_editor.games.dw7xl.dw7xl_editor import Editor
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.addCleanup(root.destroy)
        root.withdraw()
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'input.dat'
            source.write_bytes(self.document.raw)
            with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                editor = Editor(root)
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                    editor.open()
                for group, key, value in (('Weapon loadouts', 'officer_0_weapon_1', 9),
                                          ('Applied seals', 'weapon_2_applied_seal_1', 3)):
                    editor.group.set(group)
                    editor.search.set(key)
                    editor.refresh()
                    self.assertEqual(editor.fields.get_children(), (key,))
                    editor.fields.selection_set(key)
                    editor.selected()
                    label = dict(backend.field_options(editor.document, key))[value]
                    editor.choice_value.set(f'{value} · {label}')
                    editor.selected_choice()
                    editor.apply_selected()
                    self.assertEqual(editor.changes[key], value)
                    editor.max_visible()
                    self.assertEqual(editor.changes[key], value)
                editor.review()
                editor.undo()
                self.assertEqual(editor.changes, {'officer_0_weapon_1': 9})
                editor.undo()
                self.assertEqual(editor.changes, {})
                changes = {'officer_0_weapon_1': 9, 'weapon_2_applied_seal_1': 3}
                editor.stage_values(changes)
                destination = Path(folder) / 'edited.dat'
                editor.save_to(destination)
                self.assertEqual(destination.read_bytes(), backend.serialize(self.document, changes))
                self.assertEqual(source.read_bytes(), self.document.raw)
                tables = editor.presentation.inspection_tables(editor.document)
                self.assertEqual(tables[-1].title, 'Applied seals')
                self.assertTrue(tables[-1].rows)
                errors.assert_not_called()

    def test_pending_weapon_options_show_current_references_without_widening_source_pool(self):
        pending = self.adapter.stage(self.document, {}, 'officer_0_weapon_1', 9)
        active = backend.field_options_for_changes(self.document, pending, 'officer_0_active_weapon')
        self.assertEqual(dict(active)[0], 'First equipped weapon · inventory slot 10')
        self.assertEqual(dict(backend.field_options(self.document, 'officer_0_active_weapon'))[0],
                         'First equipped weapon · inventory slot 3')
        second = backend.field_options_for_changes(self.document, pending, 'officer_0_weapon_2')
        self.assertEqual([value for value, _ in second], [2, 4])
        self.assertNotIn(13, dict(second))  # Owned but never equipped in the opened copy.
        with self.assertRaises(SaveError):
            backend.field_options_for_changes(self.document, {'officer_0_weapon_1': 13},
                                              'officer_0_active_weapon')
        with self.assertRaises(SaveError):
            backend.field_options_for_changes(self.document, pending, 'unknown')
        self.assertEqual(backend.serialize(self.document, {}), self.document.raw)

    def test_pending_filled_weapon_slot_becomes_an_active_choice(self):
        document = self.mutate(backend.OFFICER_BASE + 20, b'\xff\xff')
        self.assertEqual([value for value, _ in backend.field_options(document, 'officer_0_active_weapon')],
                         [0])
        pending = self.adapter.stage(document, {}, 'officer_0_weapon_2', 9)
        choices = backend.field_options_for_changes(document, pending, 'officer_0_active_weapon')
        self.assertEqual([value for value, _ in choices], [0, 1])
        self.assertEqual(dict(choices)[1], 'Second equipped weapon · inventory slot 10')
        pending = self.adapter.stage(document, pending, 'officer_0_active_weapon', 1)
        result = self.assert_surgical(document, pending)
        self.assertEqual(equipment.word(result.payload, backend.OFFICER_BASE + 20), 9)
        self.assertEqual(equipment.word(result.payload, backend.OFFICER_BASE + 22), 1)

    def test_pending_removed_seal_frees_choice_and_preserves_opened_qualification(self):
        first, second = 'weapon_2_applied_seal_1', 'weapon_2_applied_seal_2'
        self.assertNotIn(0, dict(backend.field_options(self.document, second)))
        pending = self.adapter.stage(self.document, {}, first, equipment.EMPTY)
        choices = backend.field_options_for_changes(self.document, pending, second)
        self.assertIn(0, dict(choices))
        self.assertNotIn(2, dict(choices))  # Unlearned in the opened copy.
        self.assertIn(0, dict(backend.field_options_for_changes(self.document, pending, first)))
        with self.assertRaises(SaveError):
            backend.field_options_for_changes(self.document, pending, 'weapon_2_applied_seal_3')
        pending = self.adapter.stage(self.document, pending, second, 0)
        self.assert_surgical(self.document, pending)
        self.assertEqual(equipment.learned_seals(self.document.payload), (0, 1, 3, 7))

    def test_actual_gui_pending_choices_and_frozen_review_follow_validated_final_dependencies(self):
        import tkinter as tk
        from koei_editor.games.dw7xl.dw7xl_editor import Editor
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.addCleanup(root.destroy)
        root.withdraw()
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            opened = []
            def editor_for(document, name):
                source = folder / (name + '.dat')
                source.write_bytes(document.raw)
                host = tk.Frame(root)
                host.pack()
                editor = Editor(root, host)
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename',
                           return_value=str(source)):
                    editor.open()
                opened.append((source, document.raw))
                return editor
            def select(editor, key):
                editor.group.set('All fields')
                editor.search.set(key)
                editor.refresh()
                self.assertEqual(editor.fields.get_children(), (key,))
                editor.fields.selection_set(key)
                editor.selected()
                return {value: label for label, value in editor._choice_values.items()}
            with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                editor = editor_for(self.document, 'replaced-first')
                editor.stage_values({'officer_0_weapon_1': 9})
                active = select(editor, 'officer_0_active_weapon')
                self.assertIn('inventory slot 10', active[0])
                displayed = editor.fields.item('officer_0_active_weapon', 'values')
                self.assertIn('inventory slot 3', displayed[2])
                self.assertEqual(displayed[3], '-')
                self.assertIn('Opened: 0 · First equipped weapon · inventory slot 3',
                              editor.selection_info.get())
                self.assertIn('current: 0 · First equipped weapon · inventory slot 10',
                              editor.selection_info.get())
                second = select(editor, 'officer_0_weapon_2')
                self.assertIn(2, second)
                self.assertNotIn(9, second)
                self.assertNotIn(13, second)

                empty = self.mutate(backend.OFFICER_BASE + 20, b'\xff\xff')
                editor = editor_for(empty, 'filled-second')
                editor.stage_values({'officer_0_weapon_2': 9})
                active = select(editor, 'officer_0_active_weapon')
                self.assertIn('inventory slot 10', active[1])
                editor.choice_value.set(active[1])
                editor.selected_choice()
                editor.apply_selected()
                self.assertEqual(editor.changes, {'officer_0_weapon_2': 9,
                                                  'officer_0_active_weapon': 1})
                displayed = editor.fields.item('officer_0_active_weapon', 'values')
                self.assertIn('inventory slot 3', displayed[2])
                self.assertIn('inventory slot 10', displayed[3])
                editor.review()
                dialog = next(child for child in root.winfo_children()
                              if isinstance(child, tk.Toplevel) and child.title() == 'Review Changes')
                dialog.review_query.set('officer_0_active_weapon')
                tree = dialog.review_tree
                self.assertEqual(len(tree.get_children()), 1)
                row = tree.item(tree.get_children()[0], 'values')
                self.assertIn('inventory slot 3', row[1])
                self.assertIn('inventory slot 10', row[2])
                editor.stage_values({'officer_0_weapon_2': 4})
                dialog.review_query.set('')
                dialog.review_query.set('officer_0_active_weapon')
                self.assertEqual(tree.item(tree.get_children()[0], 'values'), row)

                editor = editor_for(self.document, 'removed-seal')
                editor.stage_values({'weapon_2_applied_seal_1': equipment.EMPTY})
                seals = select(editor, 'weapon_2_applied_seal_2')
                self.assertIn(0, seals)
                self.assertNotIn(2, seals)
                editor.choice_value.set(seals[0])
                editor.selected_choice()
                editor.apply_selected()
                self.assertEqual(editor.changes, {'weapon_2_applied_seal_1': equipment.EMPTY,
                                                  'weapon_2_applied_seal_2': 0})
                self.assertNotIn('weapon_2_applied_seal_3', backend.field_map(editor.document))
                errors.assert_not_called()
                for source, original in opened:
                    self.assertEqual(source.read_bytes(), original)

    @unittest.skipUnless(os.environ.get('DW7XL_SAVE_COPY'), 'Native PC DW7 XL copy unavailable')
    def test_native_occupied_seals_and_equipment_edits_are_surgical(self):
        document = backend.read_save(Path(os.environ['DW7XL_SAVE_COPY']))
        changed = {}
        for field in backend.fields_for(document):
            if not (equipment.reference_key(field.id) or equipment.seal_key(field.id)):
                continue
            for value, _label in backend.field_options(document, field.id):
                if value == field.value(document.payload):
                    continue
                try:
                    changed = backend.stage(document, {}, field.id, value)
                except SaveError:
                    continue
                self.assert_surgical(document, changed)
                break
            if changed:
                break
        self.assertTrue(changed, 'Native fixture must exercise a real equipment change')
        self.assertEqual(document.source.read_bytes(), document.raw)
