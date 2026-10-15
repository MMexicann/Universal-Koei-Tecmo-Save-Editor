"""Native mount ordinals, ownership qualification and protected decrease bounds."""
import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.wo3u import wo3u_equipment as equipment
from koei_editor.games.wo3u import wo3u_parser as backend
from koei_editor.games.wo3u.wo3u_editor import Editor
from koei_editor.shared.experimental_limits import experimental_limits
from tests.test_wo3u_depth import depth_raw


def mount_raw():
    raw = bytearray(depth_raw())
    # 28 and 31 are owned binary mount items. 29 is owned with an unusual
    # rank; 30 has an ordinary rank but no ownership. Neither becomes a choice.
    mask = int.from_bytes(raw[equipment.ITEM_OWNERSHIP_OFFSET:
                              equipment.ITEM_OWNERSHIP_OFFSET + 8], 'little')
    mask |= (1 << 29) | (1 << 31)
    raw[equipment.ITEM_OWNERSHIP_OFFSET:equipment.ITEM_OWNERSHIP_OFFSET + 8] = mask.to_bytes(8, 'little')
    for identity, rank in ((29, 2), (30, 1), (31, 1)):
        start = equipment.ITEM_RANK_OFFSET + 2 * identity
        raw[start:start + 2] = rank.to_bytes(2, 'little')
    raw[equipment.MOUNT_LOADOUT_OFFSETS[0]] = 0
    raw[equipment.MOUNT_LOADOUT_OFFSETS[1]] = 255
    return bytes(raw)


class WO3MountTests(unittest.TestCase):
    def test_owned_items_map_to_native_ordinals_and_change_one_byte(self):
        document = backend.decode(mount_raw())
        self.assertEqual(backend.serialize(document, {}), document.raw)
        for index, offset in enumerate(equipment.MOUNT_LOADOUT_OFFSETS):
            key = f'mount_loadout_{index}'
            field = backend.field_map(document)[key]
            self.assertEqual(field.offset, offset)
            self.assertEqual(set(dict(backend.field_options(document, key))), {0, 3, 255})
            self.assertFalse(field.maxable)
            self.assertIsNone(field.experimental_maximum)
            for value in (0, 3, 255):
                with self.subTest(loadout=index, value=value):
                    pending = backend.stage(document, {}, key, value)
                    expected = bytearray(document.raw)
                    expected[offset] = value
                    result = backend.serialize(document, pending)
                    self.assertEqual(result, expected)
                    self.assertEqual(backend.field_map(backend.decode(result))[key].value(result), value)
                    self.assertEqual(backend.stage(document, pending, key, document.raw[offset]), {})
                    self.assertEqual(backend.limit_values(document, pending, [key]), {})
                    self.assertEqual(backend.maximums(document, pending, 'Mount equipment'), pending)

    def test_unowned_unknown_and_item_ids_cannot_bypass_direct_or_staged_writes(self):
        document = backend.decode(mount_raw())
        key = 'mount_loadout_0'
        for enabled in (False, True):
            with experimental_limits(enabled):
                for value in (True, False, -1, 1, 2, 4, 16, 28, 31, 64, 254, 256, 65535, '3'):
                    for action in (lambda value=value: backend.stage(document, {}, key, value),
                                   lambda value=value: backend.serialize(document, {key: value})):
                        with self.subTest(experimental=enabled, value=value), self.assertRaises(SaveError):
                            action()

    def test_foreign_original_loadout_does_not_block_other_qualified_loadout(self):
        for value in (1, 2, 4, 16, 254):
            raw = bytearray(mount_raw())
            raw[equipment.MOUNT_LOADOUT_OFFSETS[0]] = value
            document = backend.decode(raw)
            self.assertNotIn('mount_loadout_0', backend.field_map(document))
            self.assertIn('mount_loadout_1', backend.field_map(document))
            changed = backend.serialize(document, {'mount_loadout_1': 3})
            self.assertEqual(changed[equipment.MOUNT_LOADOUT_OFFSETS[0]], value)
            self.assertEqual(backend.serialize(document, {}), raw)
            rows = [row for row in backend.inspection_rows(document)
                    if row['group'] == 'Mount equipment']
            self.assertEqual(len(rows), 2)
            self.assertIn('read only', rows[0]['value'])

    def test_no_mount_ownership_does_not_create_equipment_or_change_inventory(self):
        raw = bytearray(mount_raw())
        raw[equipment.ITEM_OWNERSHIP_OFFSET:equipment.ITEM_OWNERSHIP_OFFSET + 8] = bytes(8)
        document = backend.decode(raw)
        self.assertFalse(any(field.group == 'Mount equipment' for field in backend.fields_for(document)))
        self.assertEqual(backend.maximums(document, {}, 'Mount equipment'), {})
        self.assertEqual(backend.serialize(document, {}), raw)

    def test_two_loadouts_can_share_a_mount_and_mix_with_ordinary_equipment(self):
        document = backend.decode(mount_raw())
        pending = {'mount_loadout_0': 3, 'mount_loadout_1': 3,
                   'officer_0_equipped_item_0': 2}
        expected = bytearray(document.raw)
        for offset in equipment.MOUNT_LOADOUT_OFFSETS:
            expected[offset] = 3
        expected[backend.OFFICER_BASE + equipment.EQUIPPED_ITEM_OFFSET] = 2
        self.assertEqual(backend.serialize(document, pending), expected)
        self.assertEqual(len(backend.review(document, pending)), 3)

    def test_experimental_mode_preserves_reinforcement_decrease_only_contract(self):
        raw = bytearray(mount_raw())
        raw[backend.WEAPON_BASE + 3] = 81
        document = backend.decode(raw)
        key = 'weapon_0_reinforcement'
        with experimental_limits():
            self.assertIsNone(backend.field_map(document)[key].experimental_maximum)
            for value in (82, 99, 100, 255):
                for action in (lambda value=value: backend.stage(document, {}, key, value),
                               lambda value=value: backend.serialize(document, {key: value})):
                    with self.subTest(value=value), self.assertRaises(SaveError):
                        action()
            self.assertEqual(backend.serialize(document, {key: 80})[backend.WEAPON_BASE + 3], 80)
            for value in (100, 255):
                raw[backend.WEAPON_BASE + 3] = value
                self.assertNotIn(key, backend.field_map(backend.decode(raw)))

    def test_mount_gui_choices_review_undo_and_backup_restore(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.addCleanup(root.destroy)
        root.withdraw()
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'copy.bin'
            raw = mount_raw()
            source.write_bytes(raw)
            editor = Editor(root)
            with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                    editor.open()
                key = 'mount_loadout_0'
                editor.group.set('Mount equipment')
                editor.search.set(key)
                editor.refresh()
                self.assertEqual(editor.fields.get_children(), (key,))
                editor.fields.selection_set(key)
                editor.selected()
                editor.choice_value.set('3 · Owned mount item ID 31')
                editor.selected_choice()
                editor.apply_selected()
                self.assertEqual(editor.changes, {key: 3})
                editor.max_visible()
                self.assertEqual(editor.changes, {key: 3})
                editor.review()
                editor.undo()
                self.assertEqual(editor.changes, {})
                editor.stage_values({key: 3, 'mount_loadout_1': 0})
                expected = backend.serialize(editor.document, editor.changes)
                destination = Path(folder) / 'edited.bin'
                editor.save_to(destination)
                self.assertEqual(destination.read_bytes(), expected)
                self.assertEqual(editor.backup.read_bytes(), raw)
                restored = Path(folder) / 'restored.bin'
                backend.restore(editor.backup, restored)
                self.assertEqual(restored.read_bytes(), raw)
                self.assertEqual(source.read_bytes(), raw)
                errors.assert_not_called()


@unittest.skipUnless(os.environ.get('WO3U_SAVE_COPY'), 'Private native WO3 copy unavailable')
class NativeWO3MountTests(unittest.TestCase):
    def test_native_mount_changes_preserve_all_other_bytes_and_original(self):
        document = backend.read_save(os.environ['WO3U_SAVE_COPY'])
        fields = [field for field in backend.fields_for(document) if field.group == 'Mount equipment']
        self.assertEqual(len(fields), 2)
        self.assertEqual(backend.serialize(document, {}), document.raw)
        for field in fields:
            choices = dict(backend.field_options(document, field.id))
            self.assertEqual(set(choices), {0, 1, 2, 3, 255})
            for value in choices:
                with self.subTest(loadout=field.slot, value=value):
                    expected = bytearray(document.raw)
                    expected[field.offset] = value
                    result = backend.serialize(document, backend.stage(document, {}, field.id, value))
                    self.assertEqual(result, expected)
                    self.assertEqual(backend.field_map(backend.decode(result))[field.id].value(result), value)
        self.assertEqual(Path(document.source).read_bytes(), document.raw)
