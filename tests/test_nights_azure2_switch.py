"""Procedural nonplayable profiles, optional native copies and actual Tk flow."""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.nights_azure2_switch import parser as p
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from koei_editor.shared.experimental_limits import experimental_limits
from tests.scalar_contract import ScalarContractTests


def block(signature, revision, body):
    return struct.pack('<4sIIII', signature, 20, len(body), revision, p.fnv1a(body)) + body


def leaves(libra=5000, checkpoint=False, extra=0):
    variable = {b'#PRD': 1409 if checkpoint else 1421,
                b'#QUD': 67 if checkpoint else 200,
                b'#LID': 186, b'#FAD': 22 if checkpoint else 292,
                b'#IND': 6 if checkpoint else 36}
    variable[b'#PRD'] += extra
    output = bytearray()
    for index, (signature, revision, fixed_size) in enumerate(p.BLOCK_LAYOUT):
        size = fixed_size if fixed_size is not None else variable[signature]
        body = bytearray(bytes([0x91 + index]) * size)
        if signature == b'#PLD':
            struct.pack_into('<I', body, p.LIBRA_OFFSET, libra)
        output += block(signature, revision, bytes(body))
    return bytes(output)


def fixture(libra=5000, clear=False):
    header = bytearray(b'K' * p.ROOT_START)
    caption = b'Clear Data' if clear else b'Chapter 1: Ruined City in the Eternal Night'
    header[:len(caption) + 1] = caption + b'\0'
    preview = (b'Playtime: 002:06:15<CR>Level: 2<CR>Blood: 300<CR>Libra: '
               + str(libra).encode() + b'<CR>Servan Points: 100<CR>Ability Point: 20')
    header[p.PREVIEW_START:p.PREVIEW_START + len(preview) + 1] = preview + b'\0'
    header[0x500:0x511] = b'saveload_icon_18\0'
    current = leaves(libra)
    if clear:
        current = leaves(libra, extra=39987 - len(current))
        result = bytes(header) + block(b'#USR', 1, current)
        result += b'Q' * (91828 - len(result))
    else:
        result = bytes(header) + block(b'#USR', 1,
                                        current + block(b'#CHD', 1, leaves(777, checkpoint=True)))
    assert len(result) == (91828 if clear else 77509)
    return result


def reseal(raw, node):
    struct.pack_into('<I', raw, node.start + 16, p.fnv1a(raw[node.body_start:node.end]))


def assert_surgical(test, original, edited, value):
    layout = p._structure(original)
    field = p.field_map(p.decode(original))['libra']
    allowed = (set(range(field.offset, field.offset + 4))
               | set(range(layout.root.start + 16, layout.root.start + 20))
               | set(range(layout.current[3].start + 16, layout.current[3].start + 20))
               | set(range(p.PREVIEW_START, p.PREVIEW_START + len(layout.preview) + 1)))
    touched = {i for i, (a, b) in enumerate(zip(original, edited)) if a != b}
    test.assertTrue(touched)
    test.assertLessEqual(touched, allowed)
    test.assertEqual(len(original), len(edited))
    test.assertEqual(field.value(edited), value)
    test.assertEqual(edited[p.PREVIEW_START + len(layout.preview) + 1:p.PREVIEW_END],
                     original[p.PREVIEW_START + len(layout.preview) + 1:p.PREVIEW_END])
    test.assertEqual(edited[layout.root.end:], original[layout.root.end:])
    if layout.checkpoint:
        node = layout.checkpoint[0]
        test.assertEqual(edited[node.start:node.end], original[node.start:node.end])


class NightsAzure2FormatTests(unittest.TestCase):
    def test_native_unsigned_hash_known_answer_and_high_bit_distinction(self):
        self.assertEqual(p.fnv1a(b'foobar'), 0xBF9CF968)
        self.assertEqual(p.fnv1a(b'\x80\xff'), 0xD1390020)
        from koei_editor.research.fairy_tail_switch.codec import signed_fnv1a
        self.assertNotEqual(p.fnv1a(b'\x80\xff'), signed_fnv1a(b'\x80\xff'))

    def test_coupled_preview_scalar_hashes_and_checkpoint_preservation(self):
        for clear in (False, True):
            raw = fixture(clear=clear)
            doc = p.decode(raw)
            self.assertEqual(p.serialize(doc, {}), raw)
            self.assertEqual(p.changed_payload(doc, {}), raw)
            for value in (0, 9, 4999):
                edited = p.serialize(doc, {'libra': value})
                assert_surgical(self, raw, edited, value)
                opened = p.decode(edited)
                self.assertIn(b'Libra: ' + str(value).encode() + b'<CR>', p._structure(edited).preview)
                self.assertEqual(p.serialize(opened, {}), edited)
            self.assertEqual(p.stage(doc, {'libra': 1}, 'libra', 5000), {})
            self.assertEqual(p.review(doc, {'libra': 1})[0][1:], (5000, 1))

    def test_bounds_types_complete_pending_and_experimental_hard_constraint(self):
        doc = p.decode(fixture())
        for key, value in (('libra', -1), ('libra', 5001), ('libra', True),
                           ('libra', 1.0), ('libra', '1'), ('blood', 1), ('ability_points', 1)):
            with self.subTest(key=key, value=value), self.assertRaises(SaveError):
                p.stage(doc, {}, key, value)
        with self.assertRaises(SaveError):
            p.stage(doc, {'blood': 1}, 'libra', 1)
        for value in (None, [], 1):
            with self.assertRaises(SaveError):
                p.serialize(doc, value)
        self.assertEqual(p.maximums(doc, {'libra': 1}), {'libra': 1})
        self.assertEqual(p.limit_values(doc, {}, ['libra']), {})
        for keys in ('libra', None, [object()], ['blood']):
            with self.assertRaises(SaveError):
                p.limit_values(doc, {}, keys)
        with experimental_limits(True), self.assertRaises(SaveError):
            p.stage(doc, {}, 'libra', 5001)
        unusual = p.decode(fixture(libra=0xFFFFFFFF))
        self.assertEqual(p.field_map(unusual), {})
        self.assertEqual(p.serialize(unusual, {}), unusual.raw)

    def test_active_leaf_and_nested_leaf_corruption_survive_outer_resealing(self):
        raw = fixture()
        layout = p._structure(raw)
        for node, nested in ((layout.current[3], False), (layout.checkpoint[4], True)):
            damaged = bytearray(raw)
            damaged[node.body_start] ^= 1
            if nested:
                reseal(damaged, layout.checkpoint[0])
            reseal(damaged, layout.root)
            with self.assertRaisesRegex(SaveError, 'integrity'):
                p.decode(bytes(damaged))

    def test_header_revisions_shapes_and_foreign_formats_reject(self):
        raw = fixture()
        layout = p._structure(raw)
        mutations = ((layout.current[0].start, 1), (layout.current[0].start + 4, 1),
                     (layout.current[3].start + 12, 1),
                     (layout.checkpoint[4].start + 12, 1),
                     (layout.root.start + 12, 1))
        for offset, mask in mutations:
            damaged = bytearray(raw)
            damaged[offset] ^= mask
            if offset >= layout.checkpoint[0].body_start:
                reseal(damaged, layout.checkpoint[0])
            if offset >= layout.root.body_start:
                reseal(damaged, layout.root)
            with self.subTest(offset=offset), self.assertRaises(SaveError):
                p.decode(bytes(damaged))
        for candidate in (raw[:-1], raw + b'\0', bytes(len(raw)), bytearray(raw), list(raw), None):
            with self.assertRaises(SaveError):
                p.decode(candidate)
        with self.assertRaises(SaveError):
            p.decode(raw, 'nights_azure2_pc')
        for offset in (0, p.PREVIEW_START + 1, 0x500):
            changed = bytearray(raw)
            changed[offset] ^= 1
            with self.assertRaises(SaveError):
                p.decode(bytes(changed))

    def test_visible_libra_must_match_checksum_protected_gameplay(self):
        raw = fixture()
        layout = p._structure(raw)
        a, _ = layout.libra_span
        changed = bytearray(raw)
        changed[p.PREVIEW_START + a] = ord('4')
        with self.assertRaisesRegex(SaveError, 'disagree'):
            p.decode(bytes(changed))
        changed = bytearray(raw)
        struct.pack_into('<I', changed, layout.current[3].body_start + p.LIBRA_OFFSET, 4000)
        reseal(changed, layout.current[3])
        reseal(changed, layout.root)
        with self.assertRaisesRegex(SaveError, 'disagree'):
            p.decode(bytes(changed))

    def test_clear_inactive_tail_is_opaque_and_never_repaired(self):
        raw = bytearray(fixture(clear=True))
        for offset in (41351, 0xB804, 0xB804 + 16, len(raw) - 1):
            raw[offset] ^= 0xFF
        raw = bytes(raw)
        doc = p.decode(raw)
        self.assertEqual(p.serialize(doc, {}), raw)
        edited = p.serialize(doc, {'libra': 0})
        self.assertEqual(edited[41351:], raw[41351:])
        assert_surgical(self, raw, edited, 0)

    def test_frozen_snapshot_and_bound_adapter_native_readback(self):
        raw = fixture()
        adapter = BoundScalarAdapter(p.GAME_ID, p.EXTENSION, p)
        doc = adapter.decode(raw)
        self.assertEqual(adapter.serialize(doc, {}), raw)
        changed = adapter.serialize(doc, {'libra': 1})
        self.assertEqual(p.field_map(adapter.decode(changed))['libra'].value(changed), 1)
        for damaged in (replace(doc, raw=raw[:-1]), replace(doc, payload=raw[:-1]),
                        replace(doc, format=replace(p.FORMAT, id='other'))):
            with self.assertRaises(SaveError):
                adapter.serialize(damaged, {})
        with patch.object(p, 'serialize', return_value=raw), self.assertRaises(SaveError):
            adapter.serialize(doc, {'libra': 1})

    def test_backup_safe_save_restore_aliases_and_late_source_change(self):
        raw = fixture()
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = directory / 'SAVE_DATA_00'
            source.write_bytes(raw)
            doc = p.read_save(source)
            target = directory / 'edited'
            result = p.save_as(doc, {'libra': 0}, target)
            self.assertEqual(source.read_bytes(), raw)
            self.assertEqual(result.raw, p.serialize(doc, {'libra': 0}))
            with self.assertRaises(FileExistsError):
                p.save_as(doc, {}, source)
            with self.assertRaises(FileExistsError):
                p.save_as(doc, {}, target)
            snapshot = p.backup(doc)
            restored = p.restore(snapshot, directory / 'restored')
            self.assertEqual(restored.read_bytes(), raw)
            original_backup = p.backup
            def change_after_backup(document):
                value = original_backup(document)
                source.write_bytes(raw[:-1])
                return value
            with patch.object(p, 'backup', side_effect=change_after_backup), self.assertRaises(SaveError):
                p.save_as(doc, {}, directory / 'late-change')
            self.assertFalse((directory / 'late-change').exists())
            with self.assertRaises(SaveError):
                p.backup(doc)

    @unittest.skipUnless(os.environ.get('NOA2_SWITCH_NATIVE_DIR'), 'No separate native Nights of Azure 2 Switch copies')
    def test_optional_three_native_states_surgical_saves_and_backups(self):
        candidates = sorted(Path(os.environ['NOA2_SWITCH_NATIVE_DIR']).rglob('SAVE_DATA_*'))
        self.assertEqual(len(candidates), 3)
        originals = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in candidates}
        balances = []
        for path in candidates:
            raw = path.read_bytes()
            doc = p.read_save(path)
            field = p.field_map(doc)['libra']
            balances.append(field.maximum)
            self.assertEqual(p.serialize(doc, {}), raw)
            for value in (0, 1, field.maximum - 1):
                assert_surgical(self, raw, p.serialize(doc, {'libra': value}), value)
            with tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                copied = directory / path.name
                copied.write_bytes(raw)
                opened = p.read_save(copied)
                output = p.save_as(opened, {'libra': 1}, directory / 'edited')
                self.assertEqual(field.value(output.payload), 1)
                snapshot = p.backup(opened)
                restored = p.restore(snapshot, directory / 'restored')
                self.assertEqual(restored.read_bytes(), raw)
        self.assertEqual(sorted(balances), [205205, 228707, 9999999])
        self.assertEqual(originals, {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in candidates})


class NightsAzure2ContractTests(ScalarContractTests, unittest.TestCase):
    game_id = p.GAME_ID

    def fixture_bytes(self):
        return fixture()

    def test_noop_stage_unstage_review_and_surgical_roundtrip(self):
        # A native coupled textual preview is gameplay metadata, not a checksum
        # range to exclude from the generic surgical assertion. Check it explicitly.
        field, original, value = self.editable_value()
        self.assertEqual(self.adapter.serialize(self.document, {}), self.raw)
        pending = self.adapter.stage(self.document, {}, field.id, value)
        self.assertEqual(self.adapter.stage(self.document, pending, field.id, original), {})
        self.assertEqual([(row.id, a, b) for row, a, b in self.adapter.review(self.document, pending)],
                         [('libra', original, value)])
        raw = self.adapter.serialize(self.document, pending)
        self.assertEqual(self.adapter.changed_payload(self.document, pending), raw)
        assert_surgical(self, self.raw, raw, value)
        self.assertEqual(self.document.raw, self.raw)
        self.assertEqual(self.source.read_bytes(), self.raw)


@unittest.skipUnless(os.name == 'nt' or os.environ.get('DISPLAY'), 'Graphical display required')
class NightsAzure2GuiTests(unittest.TestCase):
    def test_open_inspect_search_edit_undo_review_theme_safe_save_and_restore(self):
        import tkinter as tk
        from koei_editor.games.nights_azure2_switch.editor import Editor
        root = tk.Tk()
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as directory:
                directory = Path(directory)
                source, target = directory / 'SAVE_DATA_00', directory / 'edited'
                native = os.environ.get('NOA2_SWITCH_NATIVE_DIR')
                raw = next(Path(native).rglob('SAVE_DATA_*')).read_bytes() if native else fixture()
                source.write_bytes(raw)
                editor = Editor(root)
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)), \
                     patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                    editor.open()
                    errors.assert_not_called()
                self.assertTrue(editor.document)
                self.assertEqual(len(editor.presentation.inspection_tables(editor.document)), 1)
                editor.show_inspector()
                root.update()
                for window in root.winfo_children():
                    if isinstance(window, tk.Toplevel):
                        window.destroy()
                editor.search.set('Libra')
                root.update()
                self.assertEqual(editor.fields.get_children(), ('libra',))
                editor.fields.selection_set('libra')
                editor.value.set('1')
                editor.apply_selected()
                self.assertEqual(editor.changes, {'libra': 1})
                editor.undo()
                self.assertEqual(editor.changes, {})
                editor.value.set('1')
                editor.apply_selected()
                editor.review()
                for window in root.winfo_children():
                    if isinstance(window, tk.Toplevel):
                        window.destroy()
                editor.apply_theme('Dark')
                with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(target)), \
                     patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                    editor.save_as()
                    errors.assert_not_called()
                self.assertEqual(p.field_map(p.read_save(target))['libra'].value(target.read_bytes()), 1)
                snapshot = next(path for path in (directory / 'WarriorsEditorBackups').iterdir() if not path.suffix)
                restored = directory / 'restored'
                with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(snapshot)), \
                     patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(restored)), \
                     patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                    editor.restore()
                    errors.assert_not_called()
                self.assertEqual(restored.read_bytes(), raw)
                self.assertEqual(source.read_bytes(), raw)
        finally:
            root.destroy()
