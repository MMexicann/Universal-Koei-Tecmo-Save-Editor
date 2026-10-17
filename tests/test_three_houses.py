"""Independent procedural Three Houses checks; these are not game-load evidence.

THREE_HOUSES_SAVE_COPY optionally names a private copied Switch slot. No native
save, identifier, checksum or game asset is checked into this test module.
"""
from dataclasses import replace
import os
from pathlib import Path
import struct
import tempfile
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.three_houses import parser as p
from koei_editor.games.three_houses.editor import Editor
from koei_editor.shared.verified_self_test import run as copied_save_test
from tests.scalar_contract import ScalarContractTests


def sealed(data):
    """Independent byte-sum integrity for the complete stored payload."""
    result = bytearray(data)
    result[:4] = (sum(result[12:]) & 0xFFFFFFFF).to_bytes(4, 'little')
    return bytes(result)


def procedural_slot(revision=23):
    """Construct layout checks, never a purported playable Switch save."""
    size, stride, player, npc_size = {
        13: (0x2540C, 0x230, 0x22AB9, 0x89B8),
        23: (0x25B2C, 0x24C, 0x231D9, 0x9048),
    }[revision]
    result = bytearray((index * 29 + 37) & 255 for index in range(size))
    struct.pack_into('<3I', result, 0, 0, revision, size)
    for index in range(400):
        struct.pack_into('<hBB', result, 12 + index * 4, -1, 0, 0)
    struct.pack_into('<hBB', result, 12, 131, 40, 3)
    struct.pack_into('<hBB', result, 16, 132, 100, 2)
    struct.pack_into('<I', result, 12 + 0x640, 2)
    for index in range(60):
        at = 12 + 0x644 + index * stride
        for slot in range(6):
            struct.pack_into('<hBB', result, at + slot * 4, -1, 0, 0)
        struct.pack_into('<h', result, at + 0x24, -1)
        result[at + 0x87] = 0
    active = 12 + 0x644
    struct.pack_into('<hBB', result, active, 137, 30, 0)
    struct.pack_into('<h', result, active + 0x24, 0)
    result[active + 0x4A] = 10
    result[active + 0x87] = 1
    struct.pack_into('<I', result, active + 0xAC, 3)
    struct.pack_into('<I', result, 12 + npc_size, 0x19DF0)
    struct.pack_into('<I', result, 12 + player + 0x1074, 12000)
    return sealed(result)


class ThreeHousesFormatTests(unittest.TestCase):
    def setUp(self):
        self.raw = procedural_slot()
        self.document = p.decode(self.raw)

    def test_complete_unchanged_roundtrip_preserves_unknown_bytes_and_higher_stats(self):
        self.assertEqual(p.serialize(self.document, {}), self.raw)
        self.assertEqual(p.maximums(self.document, {}), {})
        self.assertEqual(p.changed_payload(self.document, {}), self.document.payload)
        fields = p.field_map(self.document)
        self.assertIn('gold', fields)
        self.assertIn('convoy:0:durability', fields)
        self.assertIn('convoy:0:quantity', fields)
        self.assertIn('character:0:item:0:durability', fields)
        self.assertNotIn('convoy:1:durability', fields)
        self.assertTrue(all(not field.maxable for field in fields.values()))

    def test_revision13_retains_its_own_stride_size_and_gold_location(self):
        raw = procedural_slot(13)
        document = p.decode(raw)
        self.assertEqual(p.serialize(document, {}), raw)
        encoded = p.serialize(document, {'gold': 11999, 'character:0:item:0:durability': 29})
        allowed = set(range(4)) | set(range(12 + 0x22AB9 + 0x1074, 12 + 0x22AB9 + 0x1078))
        allowed.add(12 + 0x644 + 2)
        self.assertLessEqual({at for at, (old, new) in enumerate(zip(raw, encoded)) if old != new}, allowed)
        self.assertEqual(encoded, sealed(encoded))
        self.assertEqual(p.field_map(p.decode(encoded))['gold'].value(encoded), 11999)
        with self.assertRaises(SaveError):
            p.decode(raw + bytes(0x25B2C - len(raw)))

    def test_progression_ownership_story_supports_and_entitlement_are_not_scalar_writes(self):
        for key in ('character:0:strength', 'character:0:exp', 'character:0:class_mastery',
                    'character:0:sword_exp', 'character:0:abilities', 'character:0:combat_arts',
                    'battalion:0:exp', 'renown', 'support:0:rank', 'recruitment', 'route',
                    'story', 'reward', 'dlc_entitlement'):
            with self.subTest(key=key), self.assertRaises(SaveError):
                p.stage(self.document, {}, key, 1)

    def test_every_admitted_field_is_surgical_and_restoring_original_unstages(self):
        for field in p.fields_for(self.document):
            with self.subTest(field=field.id):
                original = field.value(self.document.payload)
                target = 'Editor' if field.kind == 'text' else max(field.minimum, original - 1)
                pending = p.stage(self.document, {}, field.id, target)
                self.assertEqual(p.stage(self.document, pending, field.id, original), {})
                encoded = p.serialize(self.document, pending)
                allowed = set(range(4)) | set(range(field.offset, field.offset + field.size))
                touched = {at for at, (old, new) in enumerate(zip(self.raw, encoded)) if old != new}
                self.assertLessEqual(touched, allowed)
                self.assertEqual(encoded, sealed(encoded))
                reopened = p.decode(encoded)
                self.assertEqual(p.field_map(reopened)[field.id].value(reopened.payload), target)
                self.assertEqual(p.serialize(self.document, {field.id: original}), self.raw)
                self.assertEqual([(row.id, before, after) for row, before, after in p.review(self.document, pending)],
                                 [(field.id, original, target)])
        self.assertEqual(self.document.raw, self.raw)

    def test_damaged_integrity_is_rejected_before_fields_or_noop_save(self):
        for offset in (0, 12, 12 + 0x644 + 0x4E, 12 + 0x231D9 + 0x1074, len(self.raw) - 1):
            damaged = bytearray(self.raw)
            damaged[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(SaveError):
                p.decode(damaged)

    def test_exact_shape_revision_and_selected_title_rejection(self):
        class SpoofLength(bytes):
            def __len__(self):
                return len(self.raw)
        SpoofLength.raw = self.raw
        for raw in (self.raw[:-1], self.raw + b'\0', SpoofLength(self.raw + b'\0'), b'\0' * len(self.raw)):
            with self.assertRaises(SaveError):
                p.decode(raw)
        for offset, value in ((4, 12), (4, 24), (8, len(self.raw) - 12), (8, 0x2540C)):
            malformed = bytearray(self.raw)
            struct.pack_into('<I', malformed, offset, value)
            with self.subTest(offset=offset, value=value), self.assertRaises(SaveError):
                p.decode(sealed(malformed))
        for game_id in ('three_hopes', 'fire_emblem_warriors', 'three_houses_pc'):
            with self.assertRaises(SaveError):
                p.decode(self.raw, game_id)

    def test_empty_or_unowned_items_are_never_created_and_infinite_durability_is_preserved(self):
        keys = ('convoy:2:quantity', 'convoy:2:durability', 'convoy:1:durability',
                'character:1:item:0:durability', 'character:0:item:0:quantity')
        for key in keys:
            with self.subTest(key=key), self.assertRaises(SaveError):
                p.stage(self.document, {}, key, 1)
        encoded = p.serialize(self.document, {'convoy:0:quantity': 1})
        self.assertEqual(encoded[16:20], self.raw[16:20])
        self.assertEqual(encoded[12 + 0x640:12 + 0x644], self.raw[12 + 0x640:12 + 0x644])

    def test_owned_record_dependencies_dead_duplicate_inactive_and_unknown_identity(self):
        active = 12 + 0x644
        for offset, data in ((active + 0xAC, struct.pack('<I', 0)),
                             (active + 0xAC, struct.pack('<I', 1)),
                             (active + 0xAC, struct.pack('<I', 2)),
                             (active + 0xAC, struct.pack('<I', 11)),
                             (active + 0x4A, b'\0'),
                             (active + 0x24, struct.pack('<h', -2)),
                             (active + 0x24, struct.pack('<h', 35)),
                             (active + 0x24, struct.pack('<h', 32767)),
                             (active + 0x24C + 0x24, struct.pack('<h', 0))):
            raw = bytearray(self.raw)
            raw[offset:offset + len(data)] = data
            raw = sealed(raw)
            document = p.decode(raw)
            self.assertNotIn('character:0:item:0:durability', p.field_map(document))
            self.assertEqual(p.serialize(document, {}), raw)
            with self.assertRaises(SaveError):
                p.serialize(document, {'character:0:item:0:durability': 1})

    def test_structural_inventory_counts_and_npc_marker_reject_even_with_repaired_integrity(self):
        for offset, data in ((12 + 0x640, struct.pack('<I', 401)),
                             (12 + 0x640, struct.pack('<I', 1)),
                             (12 + 0x644 + 0x87, b'\x07'),
                             (12 + 0x644 + 0x87, b'\0'),
                             (12 + 0x9048, struct.pack('<I', 500 * 0xD0))):
            raw = bytearray(self.raw)
            raw[offset:offset + len(data)] = data
            with self.subTest(offset=offset, data=data), self.assertRaises(SaveError):
                p.decode(sealed(raw))

    def test_higher_and_unknown_values_survive_max_unchanged_and_unstage(self):
        raw = bytearray(self.raw)
        struct.pack_into('<I', raw, 12 + 0x231D9 + 0x1074, 0xFFFFFFFF)
        struct.pack_into('<hBB', raw, 12, 131, 254, 255)
        struct.pack_into('<hBB', raw, 16, -2, 237, 217)
        document = p.decode(sealed(raw))
        self.assertEqual(p.serialize(document, p.maximums(document, {})), document.raw)
        for key, original in (('gold', 0xFFFFFFFF), ('convoy:0:durability', 254), ('convoy:0:quantity', 255)):
            self.assertEqual(p.serialize(document, {key: original}), document.raw)
            self.assertEqual(p.stage(document, {key: 1}, key, original), {})
        self.assertNotIn('convoy:1:quantity', p.field_map(document))
        # A numerically lower byte value must not grant unlimited durability.
        with self.assertRaises(SaveError):
            p.stage(document, {}, 'convoy:0:durability', 100)
        with self.assertRaises(SaveError):
            p.serialize(document, {'convoy:0:durability': 100})

    def test_unknown_positive_item_identity_is_preserved_and_never_writable(self):
        raw = bytearray(self.raw)
        struct.pack_into('<h', raw, 12, 32767)
        struct.pack_into('<h', raw, 12 + 0x644, 32767)
        document = p.decode(sealed(raw))
        for key in ('convoy:0:durability', 'convoy:0:quantity', 'character:0:item:0:durability'):
            self.assertNotIn(key, p.field_map(document))
            with self.assertRaises(SaveError):
                p.stage(document, {}, key, 1)
        self.assertEqual(p.serialize(document, {}), document.raw)
        edited = p.serialize(document, {'gold': 10})
        self.assertEqual(edited[12:16], document.raw[12:16])
        self.assertEqual(edited[12 + 0x644:12 + 0x648], document.raw[12 + 0x644:12 + 0x648])

    def test_malformed_restore_and_invalid_edit_never_create_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'slot-copy'
            source.write_bytes(self.raw)
            document = p.read_save(source)
            destination = source.with_name('invalid-edit')
            with self.assertRaises(SaveError):
                p.save_as(document, {'gold': 12001}, destination)
            self.assertFalse(destination.exists())
            snapshot = p.backup(document)
            corrupt = bytearray(snapshot.read_bytes())
            corrupt[-1] ^= 1
            snapshot.write_bytes(corrupt)
            restored = source.with_name('invalid-restore')
            with self.assertRaises(SaveError):
                p.restore(snapshot, restored)
            self.assertFalse(restored.exists())
            self.assertEqual(source.read_bytes(), self.raw)

    def test_registered_copy_self_test_reports_checksum_backups_and_game_load_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'slot-copy'
            source.write_bytes(self.raw)
            report = copied_save_test('three_houses', source, Path(folder) / 'validation')
            for key in ('success', 'checksum_verified', 'native_integrity_verified',
                        'unchanged_roundtrip', 'input_preserved', 'backup_restored'):
                self.assertTrue(report[key])
            self.assertEqual(report['integrity_kind'], 'checksum')
            self.assertEqual(report['fields_checked'], 5)
            self.assertEqual(report['fields_changed'], 0)
            self.assertFalse(report['in_game_load_tested'])
            self.assertEqual(source.read_bytes(), self.raw)

    def test_malformed_changes_increase_rejection_and_atomic_batch(self):
        for changes in (None, [], True, 'gold', {'unknown': 1}, {'gold': True}, {'gold': -1},
                        {'gold': 12001}, {'convoy:0:quantity': 0}, {'convoy:0:quantity': 4},
                        {'convoy:0:durability': 41}, {'character:0:item:0:durability': 31}):
            for action in (lambda: p.serialize(self.document, changes),
                           lambda: p.maximums(self.document, changes),
                           lambda: p.stage(self.document, changes, 'gold', 10)):
                with self.subTest(changes=changes), self.assertRaises(SaveError):
                    action()
        pending = {'gold': 10, 'convoy:0:quantity': 4}
        before = pending.copy()
        with self.assertRaises(SaveError):
            p.serialize(self.document, pending)
        self.assertEqual(pending, before)
        self.assertEqual(self.document.raw, self.raw)

    def test_source_snapshot_cannot_be_forged_mutated_or_rebound(self):
        forged = (replace(self.document, raw=bytearray(self.raw)),
                  replace(self.document, payload=memoryview(self.document.payload)),
                  replace(self.document, payload=self.document.payload[:-1] + bytes([self.document.payload[-1] ^ 1])),
                  replace(self.document, format=replace(self.document.format)))
        for document in forged:
            for action in (lambda: p.fields_for(document), lambda: p.maximums(document, {}),
                           lambda: p.serialize(document, {})):
                with self.assertRaises(SaveError):
                    action()
        with self.assertRaises(TypeError):
            replace(self.document, sha256='0' * 64)

    @unittest.skipUnless(os.environ.get('THREE_HOUSES_SAVE_COPY'), 'Private copied native Three Houses slot absent')
    def test_private_native_unchanged_and_every_exposed_surgical_edit(self):
        source = Path(os.environ['THREE_HOUSES_SAVE_COPY'])
        raw = source.read_bytes()
        # Research copies may have arbitrary private archive filenames. Admit a
        # separate extensionless copy through the application's normal path.
        with tempfile.TemporaryDirectory() as folder:
            copy = Path(folder) / 'native-slot-copy'
            copy.write_bytes(raw)
            document = p.read_save(copy)
        self.assertEqual(p.serialize(document, {}), raw)
        self.assertEqual(raw, sealed(raw))
        for field in p.fields_for(document):
            original = field.value(document.payload)
            target = 'Editor' if field.kind == 'text' else max(field.minimum, original - 1)
            if field.group == 'Motivation':
                target = 0 if original else 25
            elif field.group == 'Existing ability loadout':
                target = 240
            if target in field.forbidden:
                target -= 1
            encoded = p.serialize(document, {field.id: target})
            allowed = set(range(4)) | set(range(field.offset, field.offset + field.size))
            self.assertLessEqual({at for at, (old, new) in enumerate(zip(raw, encoded)) if old != new}, allowed)
            self.assertEqual(field.value(p.decode(encoded).payload), target)
        self.assertEqual(source.read_bytes(), raw)


class ThreeHousesContractTests(ScalarContractTests, unittest.TestCase):
    game_id = 'three_houses'
    payload_integrity_offsets = frozenset(range(4))
    fixture_bytes = staticmethod(procedural_slot)


class ThreeHousesHeadlessCallbackTests(unittest.TestCase):
    """Run inherited callbacks with mocked rendering, separately from live Tk."""
    def setUp(self):
        from koei_editor.game_registry import get_game
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.source = Path(folder.name) / 'slot-copy'
        self.raw = procedural_slot()
        self.source.write_bytes(self.raw)
        self.editor = Editor.__new__(Editor)
        editor = self.editor
        editor.adapter = get_game('three_houses').get_scalar_adapter()
        editor.layout = editor.adapter.get_format()
        editor.presentation = Editor.presentation_type(p, 'three_houses')
        editor.document = editor.adapter.read_save(self.source)
        editor.changes, editor.history, editor.backup = {}, [], None
        editor.root = Mock()
        editor.style = Mock()
        editor.style.lookup.return_value = 'TkDefaultFont'
        editor.fields, editor.value, editor.status, editor.theme_name = Mock(), Mock(), Mock(), Mock()
        editor.refresh, editor.update_filename, editor.apply_theme = Mock(), Mock(), Mock()
        editor.theme_name.get.return_value = 'Light'

    def test_inherited_batch_callbacks_undo_review_rows_and_invalid_batch_atomicity(self):
        editor = self.editor
        editor.fields.selection.return_value = ('gold', 'convoy:0:quantity')
        editor.value.get.return_value = '2'
        editor.apply_selected()
        self.assertEqual(editor.changes, {'gold': 2, 'convoy:0:quantity': 2})
        self.assertEqual(editor.history, [{}])
        before = editor.changes.copy()
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as error:
            editor.stage_values({'gold': 1, 'convoy:0:quantity': 0})
            error.assert_called_once()
        self.assertEqual(editor.changes, before)
        self.assertEqual(editor.history, [{}])
        with patch('koei_editor.shared.verified_gui.tk.Toplevel'), \
             patch('koei_editor.shared.verified_gui.ttk.Label'), \
             patch('koei_editor.shared.verified_gui.ttk.Frame'), \
             patch('koei_editor.shared.verified_gui.ttk.Scrollbar'), \
             patch('koei_editor.shared.verified_gui.ttk.Button'), \
             patch('koei_editor.shared.verified_gui.attach_sorting'), \
             patch('tkinter.font.Font') as font, \
             patch('koei_editor.shared.verified_gui.ttk.Treeview') as tree:
            font.return_value.measure.return_value = 400
            editor.review()
            values = [call.kwargs['values'][1:] for call in tree.return_value.insert.call_args_list]
            self.assertEqual(values, [('12,000', '2'), ('3', '2')])
        self.assertEqual(editor.changes, before)
        editor.undo()
        self.assertEqual(editor.changes, {})
        self.assertEqual(editor.history, [])
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_inherited_save_dialog_safe_storage_backups_restore_and_original_rejection(self):
        editor = self.editor
        editor.stage_values({'gold': 11999})
        editor.make_backup()
        self.assertEqual(editor.backup.read_bytes(), self.raw)
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as error:
            editor.save_to(self.source)
            error.assert_called_once()
        self.assertEqual(editor.changes, {'gold': 11999})
        self.assertEqual(self.source.read_bytes(), self.raw)
        destination = self.source.with_name('slot-edited')
        with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(destination)) as dialog, \
             patch('koei_editor.shared.verified_gui.messagebox.showerror') as error:
            editor.save_as()
            error.assert_not_called()
            self.assertEqual(dialog.call_args.kwargs['defaultextension'], '')
            self.assertEqual(dialog.call_args.kwargs['initialfile'], 'slot-copy-edited')
        self.assertEqual(editor.document.source, destination.resolve())
        self.assertEqual(editor.changes, {})
        self.assertEqual(editor.history, [])
        self.assertEqual(p.field_map(editor.document)['gold'].value(editor.document.payload), 11999)
        self.assertEqual(self.source.read_bytes(), self.raw)
        restored = p.restore(editor.backup, self.source.with_name('slot-restored'))
        self.assertEqual(restored.read_bytes(), self.raw)


class ThreeHousesGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.source = Path(folder.name) / 'slot-copy'
        self.raw = procedural_slot()
        self.source.write_bytes(self.raw)
        self.errors = []
        mock = patch('koei_editor.shared.verified_gui.messagebox.showerror',
                     side_effect=lambda *args: self.errors.append(args))
        mock.start()
        self.addCleanup(mock.stop)
        self.editor = Editor(self.root)
        with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(self.source)):
            self.editor.open()
        self.assertFalse(self.errors)

    def test_search_edit_review_batch_undo_inspection_max_backup_safe_save_and_restore(self):
        editor = self.editor
        field = p.field_map(editor.document)['gold']
        editor.group.set(field.group)
        editor.search.set('Gold')
        editor.refresh()
        self.assertIn('gold', editor.fields.get_children())
        editor.max_visible()
        self.assertEqual(editor.changes, {})
        editor.fields.selection_set('gold')
        editor.value.set('11999')
        editor.apply_selected()
        self.assertEqual(editor.changes, {'gold': 11999})
        editor.review()
        self.assertTrue(any(isinstance(child, tk.Toplevel) for child in self.root.winfo_children()))
        editor.undo()
        self.assertEqual(editor.changes, {})
        editor.fields.selection_set('gold')
        editor.value.set('11999')
        editor.apply_selected()
        editor.show_inspector()
        self.assertTrue(editor.presentation.inspection_tables(editor.document))
        editor.apply_theme('Dark')
        editor.apply_theme('Light')
        destination = self.source.with_name('slot-edited')
        editor.save_to(destination)
        self.assertFalse(self.errors)
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertTrue(editor.backup.exists())
        restored = p.restore(editor.backup, self.source.with_name('slot-restored'))
        self.assertEqual(restored.read_bytes(), self.raw)
        output = p.read_save(destination)
        self.assertEqual(p.field_map(output)['gold'].value(output.payload), 11999)
