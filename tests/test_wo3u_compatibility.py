"""WO3 PC conservative compatibility editing and pending-aware item selectors."""
import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.wo3u import wo3u_parser as backend
from koei_editor.games.wo3u.wo3u_editor import Editor
from koei_editor.shared.experimental_limits import experimental_limits
from tests.test_wo3u_depth import depth_raw


def compatibility_raw(value=44800):
    raw = bytearray(depth_raw())
    raw[backend.WEAPON_BASE + 20:backend.WEAPON_BASE + 24] = value.to_bytes(4, 'little')
    return bytes(raw)


class WO3CompatibilityTests(unittest.TestCase):
    def test_zero_reset_changes_only_serialized_compatibility_and_undo_is_exact(self):
        document = backend.decode(compatibility_raw())
        key = 'weapon_0_compatibility_reset'
        field = backend.field_map(document)[key]
        self.assertFalse(field.maxable)
        self.assertIsNone(field.experimental_maximum)
        self.assertEqual(backend.field_options(document, key), ())
        self.assertEqual(field.maximum, 5600)
        self.assertEqual(backend.record_label(field.slot, field.group), 'Officer 1, weapon 1')
        pending = backend.stage(document, {}, key, 0)
        expected = bytearray(document.raw)
        expected[backend.WEAPON_BASE + 20:backend.WEAPON_BASE + 24] = bytes(4)
        self.assertEqual(backend.serialize(document, pending), expected)
        self.assertEqual(backend.stage(document, pending, key, 44800), {})
        self.assertEqual([(f.id, old, new) for f, old, new in backend.review(document, pending)],
                         [(key, 44800, 0)])
        reopened = backend.decode(backend.serialize(document, pending))
        self.assertIn(key, backend.field_map(reopened))
        self.assertEqual(backend.serialize(reopened, {}), reopened.raw)
        self.assertEqual(backend.maximums(document, {}, 'Weapon compatibility'), {})
        self.assertEqual(backend.limit_values(document, {}, [key]), {})
        self.assertEqual(document.raw, compatibility_raw())

    def test_higher_values_cannot_bypass_conservative_range_in_either_editing_mode(self):
        document = backend.decode(compatibility_raw())
        key = 'weapon_0_compatibility_reset'
        for enabled in (False, True):
            with experimental_limits(enabled):
                for value in (-1, 5601, 44799, 44801, 179200, 2**32 - 1, 2**32, True, False, '0', 0.0):
                    with self.subTest(experimental=enabled, value=value):
                        with self.assertRaises(SaveError):
                            backend.stage(document, {}, key, value)
                        with self.assertRaises(SaveError):
                            backend.serialize(document, {key: value})
                self.assertEqual(backend.serialize(document, {key: 44800}), document.raw)

    def test_unusual_original_empty_weapon_and_unsupported_slots_stay_opaque(self):
        key = 'weapon_0_compatibility_reset'
        for compatibility, identity, slots in ((179201, 2, 3),
                                               (2**32 - 1, 2, 3), (44800, 65535, 3),
                                               (44800, 1395, 3), (44800, 2, 9)):
            raw = bytearray(compatibility_raw(compatibility))
            raw[backend.WEAPON_BASE:backend.WEAPON_BASE + 2] = identity.to_bytes(2, 'little')
            raw[backend.WEAPON_BASE + 2] = slots
            document = backend.decode(bytes(raw))
            for enabled in (False, True):
                with experimental_limits(enabled):
                    self.assertNotIn(key, backend.field_map(document))
                    self.assertEqual(backend.serialize(document, {}), raw)
                    maximum = backend.maximums(document, {})
                    saved = backend.serialize(document, maximum)
                    self.assertEqual(saved[backend.WEAPON_BASE + 20:backend.WEAPON_BASE + 24],
                                     raw[backend.WEAPON_BASE + 20:backend.WEAPON_BASE + 24])

    def test_item_choices_follow_complete_pending_loadout_and_original_ownership(self):
        document = backend.decode(compatibility_raw())
        first, second = 'officer_0_equipped_item_0', 'officer_0_equipped_item_1'
        self.assertEqual(set(dict(backend.field_options_for_changes(document, {}, first))), {0, 2, 255})
        cleared = backend.stage(document, {}, second, 255)
        self.assertEqual(set(dict(backend.field_options_for_changes(document, cleared, first))), {0, 1, 2, 255})
        transferred = backend.stage(document, cleared, first, 1)
        self.assertEqual(set(dict(backend.field_options_for_changes(document, transferred, second))), {0, 2, 255})
        self.assertEqual(set(dict(backend.field_options(document, first))), {0, 1, 2, 255})
        with self.assertRaises(SaveError):
            backend.field_options_for_changes(document, {first: 1}, first)
        with self.assertRaises(SaveError):
            backend.stage(document, transferred, second, 1)
        self.assertEqual(backend.field_options_for_changes(document, transferred, 'weapon_0_compatibility_reset'),
                         backend.field_options(document, 'weapon_0_compatibility_reset'))

    def test_item_inventory_distinguishes_ownership_rank_and_mount_ordinals(self):
        from koei_editor.games.wo3u import wo3u_equipment as equipment
        from koei_editor.games.wo3u.wo3u_editor import WO3Presentation
        raw = bytearray(compatibility_raw())
        raw[equipment.MOUNT_LOADOUT_OFFSETS[0]] = 0  # Ordinal zero means item 28.
        raw[equipment.MOUNT_LOADOUT_OFFSETS[1]] = 255
        unowned_rank = equipment.ITEM_RANK_OFFSET + 2 * 3
        raw[unowned_rank:unowned_rank + 2] = (65535).to_bytes(2, 'little')
        document = backend.decode(bytes(raw))
        rows = backend.item_inventory(document)
        self.assertEqual(len(rows), 64)
        self.assertTrue(rows[0]['owned'])
        self.assertEqual(rows[0]['rank'], 1)
        self.assertIn('Officer 1, item slot 1', rows[0]['references'])
        self.assertNotIn('Mount loadout 1', rows[0]['references'])
        self.assertEqual(rows[28]['kind'], 'Mount')
        self.assertIn('Mount loadout 1', rows[28]['references'])
        self.assertFalse(rows[3]['owned'])
        self.assertEqual(rows[3]['rank'], 65535)
        self.assertEqual(backend.serialize(document, {}), raw)
        table = next(table for table in WO3Presentation(backend, backend.GAME_ID).inspection_tables(document)
                     if table.title == 'Item inventory')
        self.assertEqual(len(table.rows), 64)
        self.assertIn('Read only', table.note)

    def test_save_as_native_readback_backup_restore_and_changed_source(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'copy.bin'
            source.write_bytes(compatibility_raw())
            document = backend.read_save(source)
            key = 'weapon_0_compatibility_reset'
            pending = backend.stage(document, {}, key, 0)
            destination = Path(folder) / 'edited.bin'
            reopened = backend.save_as(document, pending, destination)
            expected = bytearray(document.raw)
            expected[backend.WEAPON_BASE + 20:backend.WEAPON_BASE + 24] = bytes(4)
            self.assertEqual(reopened.raw, destination.read_bytes())
            self.assertEqual(destination.read_bytes(), expected)
            self.assertEqual(source.read_bytes(), document.raw)
            snapshots = list((source.parent / 'WarriorsEditorBackups').glob('*.bin'))
            self.assertEqual(len(snapshots), 1)
            restored = backend.restore(snapshots[0], Path(folder) / 'restored.bin')
            self.assertEqual(restored.read_bytes(), document.raw)
            source.write_bytes(compatibility_raw(100))
            with self.assertRaises(SaveError):
                backend.save_as(document, pending, Path(folder) / 'changed-source.bin')
            self.assertFalse((Path(folder) / 'changed-source.bin').exists())

    def test_gui_reset_choice_review_undo_save_and_pending_item_filter(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.addCleanup(root.destroy)
        root.withdraw()
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'copy.bin'
            source.write_bytes(compatibility_raw())
            editor = Editor(root)
            with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                    editor.open()
                key = 'weapon_0_compatibility_reset'
                editor.group.set('Weapon compatibility')
                editor.search.set(key)
                editor.refresh()
                editor.fields.selection_set(key)
                editor.selected()
                self.assertEqual(editor._choice_values, {})
                editor.value.set('0')
                editor.apply_selected()
                self.assertEqual(editor.changes, {key: 0})
                editor.review()
                editor.max_visible()
                self.assertEqual(editor.changes, {key: 0})
                editor.undo()
                self.assertEqual(editor.changes, {})
                editor.stage_values({key: 0, 'officer_0_equipped_item_1': 255})
                first = backend.field_map(editor.document)['officer_0_equipped_item_0']
                self.assertIn(1, dict(editor.field_options(first)))
                destination = Path(folder) / 'gui-edited.bin'
                editor.save_to(destination)
                self.assertEqual(destination.read_bytes()[backend.WEAPON_BASE + 20:backend.WEAPON_BASE + 24], bytes(4))
                self.assertEqual(source.read_bytes(), compatibility_raw())
                errors.assert_not_called()

    @unittest.skipUnless(os.environ.get('WO3U_SAVE_COPY'), 'Private native WO3 PC copy unavailable')
    def test_genuine_existing_weapon_resets_are_surgical_and_source_unchanged(self):
        source = Path(os.environ['WO3U_SAVE_COPY'])
        original = source.read_bytes()
        document = backend.decode(original)
        fields = [field for field in backend.fields_for(document)
                  if isinstance(field, backend.CompatibilityField)]
        self.assertGreater(len(fields), 5)
        for field in fields:
            expected = bytearray(original)
            expected[field.offset:field.offset + 4] = bytes(4)
            self.assertEqual(backend.serialize(document, {field.id: 0}), expected)
            self.assertEqual(field.value(backend.decode(bytes(expected)).payload), 0)
        self.assertEqual(source.read_bytes(), original)
