"""Native WO3 PC balance bounds and descriptor-independent compatibility edits."""
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
from tests.test_wo3u_compatibility import compatibility_raw


class NativeBalanceBoundTests(unittest.TestCase):
    def test_current_crystal_word_and_expanded_gems_are_surgical(self):
        document = backend.decode(compatibility_raw())
        for key, offset, width, values in (
                ('crystals', 0xD5DC, 2, (0, 255, 256, 999)),
                ('gems', 0x137C, 4, (0, 999999, 1000000, 9999999))):
            field = backend.field_map(document)[key]
            self.assertEqual((field.offset, field.size), (offset, width))
            self.assertFalse(field.maxable)
            for value in values:
                with self.subTest(key=key, value=value):
                    expected = bytearray(document.raw)
                    expected[offset:offset + width] = value.to_bytes(width, 'little')
                    pending = backend.stage(document, {}, key, value)
                    result = backend.serialize(document, pending)
                    self.assertEqual(result, expected)
                    self.assertEqual(field.value(backend.decode(result).payload), value)
                    self.assertEqual(backend.stage(document, pending, key, field.value(document.raw)), {})
                    # Lifetime gem/crystal counters are separate, including at zero.
                    self.assertEqual(result[0xE7B0:0xE7B8], document.raw[0xE7B0:0xE7B8])
            for value in (-1, field.maximum + 1, True, False, '1', 1.0):
                with self.subTest(key=key, invalid=value), self.assertRaises(SaveError):
                    backend.serialize(document, {key: value})
        self.assertEqual(backend.maximums(document, {}, 'Resources'), {})
        self.assertEqual(backend.limit_values(document, {}, ['crystals', 'gems']), {})

    def test_unusual_original_resources_undo_and_experimental_storage_bounds(self):
        raw = bytearray(compatibility_raw())
        raw[0xD5DC:0xD5DE] = (65535).to_bytes(2, 'little')
        raw[0x137C:0x1380] = (2**32 - 1).to_bytes(4, 'little')
        document = backend.decode(raw)
        self.assertEqual(backend.serialize(document, {}), raw)
        for key in ('crystals', 'gems'):
            field = backend.field_map(document)[key]
            pending = backend.stage(document, {}, key, 1)
            self.assertEqual(backend.stage(document, pending, key, field.value(raw)), {})
            self.assertEqual(backend.serialize(document, {key: field.value(raw)}), raw)
            self.assertEqual(backend.review(document, {key: field.value(raw)}), [])
            with experimental_limits(True):
                self.assertEqual(field.experimental_maximum, (1 << (8 * field.size)) - 1)
                higher = field.maximum + 1
                edited = backend.serialize(document, backend.stage(document, {}, key, higher))
                self.assertEqual(field.value(backend.decode(edited).payload), higher)
                with self.assertRaises(SaveError):
                    backend.stage(document, {}, key, field.experimental_maximum + 1)
        self.assertEqual(backend.maximums(document, {}, 'Resources'), {})

    def test_typed_original_noops_do_not_hide_invalid_pending_dependencies(self):
        document = backend.decode(compatibility_raw())
        first, second = 'officer_0_equipped_item_0', 'officer_0_equipped_item_1'
        for operation in (backend.serialize, backend.review):
            # The exact original second selector drops out, leaving an invalid
            # duplicate in the final loadout. It must still be rejected.
            with self.assertRaises(SaveError):
                operation(document, {first: 1, second: 1})
            for value in (True, False, 0.0, '0'):
                with self.subTest(value=value), self.assertRaises(SaveError):
                    operation(document, {'crystals': value})
            with self.assertRaises(SaveError):
                operation(document, {'unknown': 0, 'crystals': 0})

    def test_compatibility_range_includes_zero_originals_and_restores_higher_originals(self):
        key = 'weapon_0_compatibility_reset'  # Existing field ID is stable.
        for opened in (0, 1, 5600, 5601, 44800, 179200):
            document = backend.decode(compatibility_raw(opened))
            field = backend.field_map(document)[key]
            self.assertEqual(field.maximum, 5600)
            self.assertIsNone(field.experimental_maximum)
            self.assertFalse(field.maxable)
            self.assertEqual(backend.field_options(document, key), ())
            for value in (0, 1, 1400, 5599, 5600):
                with self.subTest(opened=opened, value=value):
                    pending = backend.stage(document, {}, key, value)
                    expected = bytearray(document.raw)
                    expected[field.offset:field.offset + 4] = value.to_bytes(4, 'little')
                    edited = backend.serialize(document, pending)
                    self.assertEqual(edited, expected)
                    self.assertEqual(backend.field_map(backend.decode(edited))[key].value(edited), value)
                    self.assertEqual(backend.stage(document, pending, key, opened), {})
            # The opened exception does not admit other descriptor-dependent values.
            for enabled in (False, True):
                with experimental_limits(enabled):
                    for value in (5601, 89600, 179200, 179201):
                        if value != opened:
                            with self.subTest(opened=opened, invalid=value), self.assertRaises(SaveError):
                                backend.serialize(document, {key: value})
            self.assertEqual(backend.maximums(document, {}, 'Weapon compatibility'), {})

    def test_compatibility_unknown_weapon_or_larger_original_is_not_promoted(self):
        key = 'weapon_0_compatibility_reset'
        for identity, slots, opened in ((1395, 2, 0), (65535, 2, 0),
                                        (2, 9, 0), (2, 2, 179201)):
            raw = bytearray(compatibility_raw(opened))
            raw[backend.WEAPON_BASE:backend.WEAPON_BASE + 2] = identity.to_bytes(2, 'little')
            raw[backend.WEAPON_BASE + 2] = slots
            document = backend.decode(raw)
            for enabled in (False, True):
                with experimental_limits(enabled):
                    self.assertNotIn(key, backend.field_map(document))
                    with self.assertRaises(SaveError):
                        backend.serialize(document, {key: 5600})
            self.assertEqual(backend.serialize(document, {}), raw)

    def test_gui_numeric_edit_review_undo_backup_save_restore(self):
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
                editor.group.set('Resources')
                editor.search.set('crystals')
                editor.refresh()
                editor.fields.selection_set('crystals')
                editor.selected()
                editor.value.set('999')
                editor.apply_selected()
                self.assertEqual(editor.changes, {'crystals': 999})
                editor.max_visible()
                editor.review()
                self.assertEqual(editor.changes, {'crystals': 999})
                editor.undo()
                self.assertEqual(editor.changes, {})
                editor.stage_values({'gems': 2000000, 'crystals': 999,
                                     'weapon_0_compatibility_reset': 5600})
                expected = backend.serialize(editor.document, editor.changes)
                destination = Path(folder) / 'edited.bin'
                editor.save_to(destination)
                self.assertEqual(destination.read_bytes(), expected)
                self.assertEqual(editor.backup.read_bytes(), source.read_bytes())
                restored = Path(folder) / 'restored.bin'
                backend.restore(editor.backup, restored)
                self.assertEqual(restored.read_bytes(), source.read_bytes())
                errors.assert_not_called()


@unittest.skipUnless(os.environ.get('WO3U_SAVE_COPY'), 'Private native WO3 copy unavailable')
class NativeBalanceCopyTests(unittest.TestCase):
    def test_existing_compatibility_and_current_resources_roundtrip_surgically(self):
        source = Path(os.environ['WO3U_SAVE_COPY'])
        raw = source.read_bytes()
        document = backend.read_save(source)
        fields = tuple(field for field in backend.fields_for(document)
                       if isinstance(field, backend.CompatibilityField))
        self.assertGreater(len(fields), 5)
        self.assertEqual(backend.serialize(document, {}), raw)
        for compatibility, gems, crystals in ((0, 1000000, 0), (5600, 9999999, 999)):
            pending = {field.id: compatibility for field in fields}
            pending.update(gems=gems, crystals=crystals)
            expected = bytearray(raw)
            for field in fields:
                expected[field.offset:field.offset + 4] = compatibility.to_bytes(4, 'little')
            expected[0x137C:0x1380] = gems.to_bytes(4, 'little')
            expected[0xD5DC:0xD5DE] = crystals.to_bytes(2, 'little')
            edited = backend.serialize(document, pending)
            self.assertEqual(edited, expected)
            self.assertEqual(edited[0xE7B0:0xE7B8], raw[0xE7B0:0xE7B8])
            reopened = backend.decode(edited)
            self.assertEqual(backend.serialize(reopened, {}), edited)
        self.assertEqual(source.read_bytes(), raw)
