"""Procedural, non-playable fixtures for native Gemfire record qualification."""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.gemfire_nes import parser as nes
from koei_editor.games.gemfire_snes import parser as snes
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from tests.scalar_contract import ScalarContractTests


def procedural_raw(platform='nes', bases=(0x800, 0x1000)):
    """Distinct opaque bytes, two qualified blocks and one enemy province each."""
    ram_base = 0x6000 if platform == 'nes' else 0xC004
    month_offset, player_offset = (7, 0x28) if platform == 'nes' else (3, 0x24)
    raw = bytearray((index * 13 + 31) & 255 for index in range(8192))
    for block_index, base in enumerate(bases):
        raw[base + month_offset] = 5
        raw[base + player_offset:base + player_offset + 2] = bytes((0, 255))
        raw[base + 0x765:base + 0x769] = b'KOEI'
        for index in range(30):
            army = base + 0x35 + index * 4
            raw[army:army + 4] = bytes((255, 255, 255, 0))
        raw[base + 0x35:base + 0x39] = bytes((11, 0, 255, 0))
        raw[base + 0x39:base + 0x3D] = bytes((12, 1, 255, 0))
        for index in range(64):
            leader = base + 0xAD + index * 10
            raw[leader:leader + 2] = b'\0\0'
            raw[leader + 5:leader + 7] = bytes((255, 255))
        raw[base + 0xAD + 5:base + 0xAD + 7] = bytes((0, 0))
        raw[base + 0xAD + 15:base + 0xAD + 17] = bytes((1, 1))
        for index in range(30):
            record = base + 0x32D + index * 36
            raw[record:record + 2] = b'\0\0'
            raw[record + 14] = 255
        for index in (0, 1):
            record = base + 0x32D + index * 36
            raw[record:record + 2] = (ram_base + 0xAD + index * 10).to_bytes(2, 'little')
            raw[record + 14] = index
            raw[record + 2:record + 4] = (321 + block_index).to_bytes(2, 'little')
            raw[record + 4:record + 6] = (456 + block_index).to_bytes(2, 'little')
            raw[record + 8:record + 11] = bytes((70, 80, 90))
    return bytes(raw)


class GemfireNativeTests(unittest.TestCase):
    def adapters(self):
        return ((nes, BoundScalarAdapter(nes.GAME_ID, '.sav', nes)),
                (snes, BoundScalarAdapter(snes.GAME_ID, '.srm', snes)))

    def test_noop_dynamic_record_locations_and_platform_pointer_identity(self):
        for backend, adapter in self.adapters():
            with self.subTest(game=backend.GAME_ID):
                raw = procedural_raw(backend.GAME_ID.rsplit('_', 1)[1], (0x40, 0x1200))
                doc = adapter.decode(raw)
                self.assertEqual(adapter.serialize(doc, {}), raw)
                self.assertEqual(len(adapter.fields_for(doc)), 10)
                self.assertIn('state_0040_province_0_gold', adapter.field_map(doc))
                self.assertIn('state_1200_province_0_gold', adapter.field_map(doc))
                self.assertNotIn('state_0040_province_1_gold', adapter.field_map(doc))
                self.assertEqual(len(backend.province_records(doc)), 60)
                self.assertFalse(doc.format.sample_verified)
                self.assertFalse(doc.format.game_load_verified)
                foreign = snes if backend is nes else nes
                with self.assertRaises(SaveError):
                    foreign.decode(raw)

    def test_all_fields_surgical_and_enemy_soldiers_unknown_bytes_preserved(self):
        for backend, adapter in self.adapters():
            doc = adapter.decode(procedural_raw(backend.GAME_ID.rsplit('_', 1)[1]))
            fields = adapter.field_map(doc)
            changes = {key: field.maximum for key, field in fields.items()}
            encoded = adapter.serialize(doc, changes)
            reopened = adapter.decode(encoded)
            allowed = {offset for field in fields.values()
                       for offset in range(field.offset, field.offset + field.size)}
            touched = {index for index, pair in enumerate(zip(encoded, doc.raw)) if pair[0] != pair[1]}
            self.assertTrue(touched)
            self.assertLessEqual(touched, allowed)
            for key, value in changes.items():
                self.assertEqual(fields[key].value(reopened.payload), value)
            for base in (0x800, 0x1000):
                record = base + 0x32D
                self.assertEqual(encoded[record + 6:record + 8], doc.raw[record + 6:record + 8])
                enemy = record + 36
                self.assertEqual(encoded[enemy:enemy + 36], doc.raw[enemy:enemy + 36])
            self.assertEqual(doc.raw, doc.payload)

    def test_unusual_opened_values_are_typed_noops_and_max_preserves_them(self):
        for backend, adapter in self.adapters():
            raw = bytearray(procedural_raw(backend.GAME_ID.rsplit('_', 1)[1]))
            raw[0x800 + 0x32D + 2:0x800 + 0x32D + 4] = (60000).to_bytes(2, 'little')
            raw[0x800 + 0x32D + 8] = 201
            doc = adapter.decode(raw)
            gold = 'state_0800_province_0_gold'
            loyalty = 'state_0800_province_0_loyalty'
            self.assertEqual(adapter.stage(doc, {}, gold, 60000), {})
            self.assertEqual(adapter.stage(doc, {gold: 500}, gold, 60000), {})
            self.assertEqual(adapter.serialize(doc, {gold: 60000, loyalty: 201}), bytes(raw))
            maxima = adapter.maximums(doc, {})
            self.assertNotIn(gold, maxima)
            self.assertNotIn(loyalty, maxima)
            edited = adapter.serialize(doc, maxima)
            self.assertEqual(adapter.field_map(doc)[gold].value(edited), 60000)
            for value in (True, 60000.0, '60000', None, -1, 1000):
                with self.subTest(value=value), self.assertRaises(SaveError):
                    adapter.stage(doc, {}, gold, value)

    def test_structure_owner_dependencies_broken_chains_and_footer_rejected(self):
        for backend, adapter in self.adapters():
            raw = procedural_raw(backend.GAME_ID.rsplit('_', 1)[1])
            ram_base = 0x6000 if backend is nes else 0xC004
            month_offset, player_offset = (7, 0x28) if backend is nes else (3, 0x24)
            mutations = (
                (0x800 + month_offset, b'\0'), (0x800 + player_offset, bytes((30,))),
                (0x800 + 0x35 + 1, bytes((255,))),
                (0x800 + 0x32D + 14, bytes((1,))),
                (0x800 + 0xAD + 5, bytes((1,))),
                (0x800 + 0x32D, (ram_base + 0xAE).to_bytes(2, 'little')),
                (0x800 + 0xAD, (ram_base + 0xAD).to_bytes(2, 'little')),
                (0x800 + 0x32D + 36, (ram_base + 0xAD).to_bytes(2, 'little')),
                (0x1000 + 0x765, b'XOEI'),
            )
            for offset, value in mutations:
                bad = bytearray(raw)
                bad[offset:offset + len(value)] = value
                if offset == 0x1000 + 0x765:
                    # No checksum/header for an unoccupied native block; an
                    # absent marker leaves opaque bytes intact, not repaired.
                    self.assertEqual(len(adapter.fields_for(adapter.decode(bad))), 5)
                else:
                    with self.subTest(game=backend.GAME_ID, offset=offset), self.assertRaises(SaveError):
                        adapter.decode(bad)
            for bad in (raw[:-1], raw + b'X', b'\0' * 8192, b'\xff' * 8192, b'NES\x1a' + raw):
                with self.assertRaises(SaveError):
                    adapter.decode(bad)
            bad = bytearray(raw)
            bad[1:5] = b'KOEI'
            with self.assertRaises(SaveError):
                adapter.decode(bad)

    def test_snapshot_foreign_identity_and_entire_pending_map_are_checked(self):
        for backend, adapter in self.adapters():
            doc = adapter.decode(procedural_raw(backend.GAME_ID.rsplit('_', 1)[1]))
            key = 'state_0800_province_0_gold'
            for pending in (None, [], {'unknown': 1}, {key: True}):
                with self.assertRaises(SaveError):
                    adapter.stage(doc, pending, key, 500)
            for invalid_key in ([], None, '__unknown__'):
                with self.assertRaises(SaveError):
                    adapter.stage(doc, {}, invalid_key, 500)
            foreign = replace(doc, format=replace(doc.format, id='different'))
            with self.assertRaises(SaveError):
                adapter.serialize(foreign, {})
            tampered = replace(doc, payload=doc.payload[:-1] + b'\x11')
            with self.assertRaises(SaveError):
                adapter.serialize(tampered, {})

    def test_backend_safe_storage_on_disk_readback_and_changed_sources(self):
        for backend, adapter in self.adapters():
            with tempfile.TemporaryDirectory() as folder:
                folder = Path(folder)
                path = folder / ('input' + backend.EXTENSION)
                raw = procedural_raw(backend.GAME_ID.rsplit('_', 1)[1])
                path.write_bytes(raw)
                doc = adapter.read_save(path)
                target = folder / ('edited' + backend.EXTENSION)
                changes = {'state_0800_province_0_gold': 500}
                reopened = adapter.save_as(doc, changes, target)
                self.assertEqual(path.read_bytes(), raw)
                self.assertEqual(reopened.raw, target.read_bytes())
                backups = list((folder / 'WarriorsEditorBackups').glob('**/*' + backend.EXTENSION))
                self.assertTrue(backups)
                restored = folder / ('restored' + backend.EXTENSION)
                adapter.restore(backups[0], restored)
                self.assertEqual(restored.read_bytes(), raw)
                with self.assertRaises(FileExistsError):
                    adapter.save_as(doc, {}, target)
                path.write_bytes(raw[:-1])
                with self.assertRaises(SaveError):
                    adapter.save_as(doc, changes, folder / ('changed' + backend.EXTENSION))
                self.assertFalse((folder / ('changed' + backend.EXTENSION)).exists())

    def test_bound_adapter_rejects_writer_that_drops_requested_values(self):
        adapter = BoundScalarAdapter(nes.GAME_ID, '.sav', nes)
        doc = adapter.decode(procedural_raw())
        with patch.object(nes, 'serialize', return_value=doc.raw), self.assertRaises(SaveError):
            adapter.serialize(doc, {'state_0800_province_0_gold': 500})

    def test_changed_source_during_backup_and_disk_write_mismatch_rejected(self):
        from koei_editor.games.gemfire_sram import parser as core
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'copy.sav'
            raw = procedural_raw()
            source.write_bytes(raw)
            doc = nes.read_save(source)
            original_backup = core.snapshot_backup

            def changed_during_backup(*args, **kwargs):
                result = original_backup(*args, **kwargs)
                source.write_bytes(b'changed while backup completed')
                return result

            with patch.object(core, 'snapshot_backup', side_effect=changed_during_backup), self.assertRaises(SaveError):
                nes.save_as(doc, {}, folder / 'race.sav')
            self.assertFalse((folder / 'race.sav').exists())
            source.write_bytes(raw)

            def corrupted_disk_write(data, path):
                path.write_bytes(data[:-1])

            with patch.object(core, 'atomic_new', side_effect=corrupted_disk_write), self.assertRaises(SaveError):
                nes.save_as(doc, {'state_0800_province_0_gold': 500}, folder / 'bad-disk.sav')
            self.assertEqual(source.read_bytes(), raw)

    def test_optional_copied_native_images(self):
        found = False
        for backend, adapter in self.adapters():
            variable = 'GEMFIRE_' + backend.GAME_ID.rsplit('_', 1)[1].upper() + '_SAVE_COPY'
            path = os.environ.get(variable)
            if path:
                found = True
                doc = adapter.read_save(Path(path))
                self.assertEqual(adapter.serialize(doc, {}), doc.raw)
                self.assertTrue(adapter.fields_for(doc))
        if not found:
            self.skipTest('No separately reviewed native Gemfire battery images configured.')


class GemfireNESContractTests(ScalarContractTests, unittest.TestCase):
    game_id = 'gemfire_nes'

    def fixture_bytes(self):
        return procedural_raw('nes')


class GemfireSNESContractTests(ScalarContractTests, unittest.TestCase):
    game_id = 'gemfire_snes'

    def fixture_bytes(self):
        return procedural_raw('snes')


class GemfireGuiTests(unittest.TestCase):
    def test_both_editors_search_stage_review_undo_and_safe_copy_save(self):
        from koei_editor.games.gemfire_nes.editor import Editor as NESEditor
        from koei_editor.games.gemfire_snes.editor import Editor as SNESEditor
        try:
            root = tk.Tk()
            root.geometry('1080x820')
        except tk.TclError as error:
            self.skipTest(str(error))
        try:
            for backend, editor_type in ((nes, NESEditor), (snes, SNESEditor)):
                with tempfile.TemporaryDirectory() as directory:
                    source = Path(directory) / ('copy' + backend.EXTENSION)
                    raw = procedural_raw(backend.GAME_ID.rsplit('_', 1)[1])
                    source.write_bytes(raw)
                    host = ttk.Frame(root)
                    host.pack(fill='both', expand=True)
                    editor = editor_type(root, parent=host, theme='Dark')
                    with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)), \
                         patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                        editor.open()
                        errors.assert_not_called()
                    root.update()
                    self.assertEqual(len(editor.presentation.inspection_tables(editor.document)[0].rows), 60)
                    key = 'state_0800_province_0_gold'
                    editor.search.set(key)
                    root.update()
                    self.assertEqual(editor.fields.get_children(), (key,))
                    editor.fields.selection_set(key)
                    editor.selected()
                    editor.value.set('999')
                    editor.apply_selected()
                    self.assertEqual(editor.changes, {key: 999})
                    editor.undo()
                    self.assertEqual(editor.changes, {})
                    editor.value.set('999')
                    editor.apply_selected()
                    editor.review()
                    dialog = next(child for child in root.winfo_children() if isinstance(child, tk.Toplevel))
                    dialog.destroy()
                    destination = Path(directory) / ('edited' + backend.EXTENSION)
                    with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(destination)), \
                         patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
                        editor.save_as()
                        errors.assert_not_called()
                    reopened = backend.read_save(destination)
                    self.assertEqual(backend.field_map(reopened)[key].value(reopened.payload), 999)
                    self.assertEqual(source.read_bytes(), raw)
                    host.destroy()
        finally:
            root.destroy()
