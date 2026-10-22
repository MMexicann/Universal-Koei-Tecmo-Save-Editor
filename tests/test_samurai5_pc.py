"""Procedural safety checks, plus opt-in genuine native copied-save qualification."""
from dataclasses import replace
import json
import os
from pathlib import Path
import secrets
import shutil
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.samurai5_pc import codec, parser
from koei_editor.games.samurai5_pc.presentation import Presentation
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from koei_editor.shared.steam_owner import read_owner
from tests.scalar_contract import ScalarContractTests
from tests.gui_paging import assert_paged_catalog


def sidecar(folder):
    value = secrets.randbelow(0xFFFFFFFF) + 1
    path = Path(folder) / 'steam_autocloud.vdf'
    path.write_bytes(f'"steam_autocloud.vdf"\n{{\n "accountid" "{value}"\n}}\n'.encode())
    return path

def procedural(owner):
    payload = bytearray(codec.SAVE_SIZE - 4)
    struct.pack_into('<II', payload, 0, 39, 39)
    payload[-16:] = codec.FINGERPRINT
    payload[codec.MANAGER_END] = 1
    for state, kind, start, count, stride in codec.SECTIONS:
        if kind not in (1, 4):
            payload[start:start + min(4, stride)] = bytes((state, kind, 0xA5, 0x5A))[:min(4, stride)]
        if kind == 4:
            struct.pack_into('<II', payload, start + 12, 100 + state, 800 + state)
    for item in parser.FIELDS:
        payload[item.offset:item.offset + item.size] = min(37, item.maximum).to_bytes(item.size, 'little')
    payload[codec.MANAGER_END + 100:codec.MANAGER_END + 104] = b'OLD!'
    payload[codec.SECOND_RESUME + 100:codec.SECOND_RESUME + 104] = b'LAST'
    return codec.encode_file(bytes(payload), owner.account_id, secrets.randbits(32))

class Samurai5ContractTests(ScalarContractTests, unittest.TestCase):
    game_id = parser.GAME_ID
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.source = self.folder / 'input-copy.bin'
        sidecar(self.folder)
        self.raw = procedural(read_owner(self.source))
        self.source.write_bytes(self.raw)
        self.game = SimpleNamespace(extension='.bin')
        self.adapter = BoundScalarAdapter(parser.GAME_ID, '.bin', parser)
        self.document = self.adapter.read_save(self.source)

    def test_noop_stage_unstage_review_and_surgical_roundtrip(self):
        # Owner-dependent decode requires an explicit copied-save source.
        doc, adapter = self.document, self.adapter
        self.assertEqual(adapter.serialize(doc, {}), self.raw)
        item, before, after = self.editable_value()
        changes = adapter.stage(doc, {}, item.id, after)
        self.assertEqual(adapter.stage(doc, changes, item.id, before), {})
        self.assertEqual([(f.id, old, new) for f, old, new in adapter.review(doc, changes)], [(item.id, before, after)])
        reopened = adapter.decode(adapter.serialize(doc, changes), source=self.source)
        self.assertEqual(reopened.payload, adapter.changed_payload(doc, changes))
        self.assertEqual(reopened.payload[:item.offset], doc.payload[:item.offset])
        self.assertEqual(reopened.payload[item.offset + item.size:], doc.payload[item.offset + item.size:])
        with self.assertRaises(SaveError):
            adapter.decode(self.raw)
        self.assertEqual(self.source.read_bytes(), self.raw)

class Samurai5SafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.source = self.folder / 'input-copy.bin'
        self.companion = sidecar(self.folder)
        self.owner = read_owner(self.source)
        self.raw = procedural(self.owner)
        self.source.write_bytes(self.raw)
        self.doc = parser.read_save(self.source)

    def test_generated_held_gem_catalog_pages_and_off_page_edit_undo_save(self):
        """Generated held stacks qualify paging, not native player-save support."""
        import tkinter as tk
        from koei_editor.games.samurai5_pc.editor import Editor
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest('Tk display unavailable.')
        self.addCleanup(root.destroy)
        payload = bytearray(self.doc.payload)
        for index in range(parser.GEM_COUNT):
            payload[parser.GEM_BASE + index] = 1 if index % 10 else 0
        raw = codec.encode_file(bytes(payload), self.owner.account_id, 7)
        self.source.write_bytes(raw)
        editor = Editor(root, parent=root)
        with patch('koei_editor.shared.verified_gui.messagebox.showerror') as errors:
            self.assertTrue(editor.open_path(self.source))
            fields = parser.fields_for(editor.document)
            self.assertEqual(len(fields), len(parser.FIELDS) + 900)
            assert_paged_catalog(self, editor, (field.id for field in fields))
            last = fields[-1]
            self.assertTrue(editor.navigate_dashboard_field(last.id))
            self.assertGreater(editor._field_page, 0)
            self.assertEqual(editor.fields.selection(), (last.id,))
            editor.value.set('2')
            editor.apply_selected()
            self.assertEqual(editor.changes, {last.id: 2})
            editor.undo()
            self.assertEqual(editor.changes, {})
            editor.stage_values({last.id: 2})
            destination = self.folder / 'paged-edited.bin'
            editor.save_to(destination)
        errors.assert_not_called()
        saved = parser.read_save(destination)
        self.assertEqual(last.value(saved.payload), 2)
        self.assertEqual(self.source.read_bytes(), raw)
        self.assertEqual(editor.backup.read_bytes(), raw)

    def test_seven_fields_surgical_checkpoint_unknowns_and_caps(self):
        self.assertEqual(len(parser.fields_for(self.doc)), 7)
        for item in parser.FIELDS:
            with self.subTest(field=item.id):
                changes = parser.stage(self.doc, {}, item.id, item.maximum)
                payload = parser.changed_payload(self.doc, changes)
                self.assertEqual(payload[:item.offset], self.doc.payload[:item.offset])
                self.assertEqual(payload[item.offset + item.size:], self.doc.payload[item.offset + item.size:])
                self.assertEqual(parser.stage(self.doc, changes, item.id, item.value(self.doc.payload)), {})
        changes = parser.maximums(self.doc, {})
        encoded = parser.serialize(self.doc, changes)
        reopened = parser.decode(encoded, source=self.source)
        self.assertEqual(reopened.payload, parser.changed_payload(self.doc, changes))
        self.assertEqual(reopened.payload[0x63420:], self.doc.payload[0x63420:])
        self.assertEqual(reopened.payload[0xD8:0xDC], self.doc.payload[0xD8:0xDC])
        tables = Presentation(parser, parser.GAME_ID).inspection_tables(reopened)
        self.assertGreater(len(tables), 10)
        self.assertEqual(len(tables[1].rows), 4)

    def test_unusual_higher_values_preserved_by_max_and_unstage(self):
        payload = bytearray(self.doc.payload)
        for item in parser.FIELDS:
            payload[item.offset:item.offset + item.size] = (item.maximum + 1).to_bytes(item.size, 'little')
        doc = parser.decode(codec.encode_file(bytes(payload), self.owner.account_id, 7), owner=self.owner)
        self.assertEqual(parser.maximums(doc, {}), {})
        for item in parser.FIELDS:
            changes = parser.stage(doc, {}, item.id, 1)
            self.assertEqual(parser.maximums(doc, changes), {})
            self.assertEqual(parser.stage(doc, changes, item.id, item.maximum + 1), {})
        self.assertEqual(parser.serialize(doc, {}), doc.raw)

    def test_revision_resume_fingerprint_alignment_and_ciphertext_rejection(self):
        for offset, value in ((0, 38), (4, 38), (codec.SECOND_RESUME, 1),
                              (codec.SECOND_RESUME, 2), (codec.MANAGER_END, 2),
                              (codec.PAD_START, 1), (len(self.doc.payload) - 1, 0)):
            with self.subTest(offset=offset, value=value):
                malformed = bytearray(self.doc.payload)
                malformed[offset] = value
                with self.assertRaises(SaveError):
                    codec.validate_payload(bytes(malformed))
        for raw in (b'', self.raw[:-1], self.raw + b'\0', self.doc.payload,
                    self.raw[:-20] + bytes(20)):
            with self.assertRaises(SaveError):
                parser.decode(raw, owner=self.owner)
        wrong = self.folder / 'wrong'
        wrong.mkdir()
        sidecar(wrong)
        with self.assertRaises(SaveError):
            parser.decode(self.raw, owner=read_owner(wrong / 'copy.bin'))
        with self.assertRaises(SaveError):
            parser.decode(self.raw, 'samurai4dx', self.source)
        for forged in (replace(self.doc, payload=self.doc.payload[:-1] + b'!'),
                       replace(self.doc, format=replace(parser.FORMAT)),
                       replace(self.doc, owner=read_owner(wrong / 'copy.bin'))):
            with self.assertRaises(SaveError):
                parser.serialize(forged, {})

    def test_owner_context_destination_backup_restore_and_private_repr(self):
        self.assertNotIn(self.owner.raw.decode().strip(), repr(self.doc))
        self.assertNotIn(str(self.source), repr(self.doc))
        other = self.folder / 'other'
        other.mkdir()
        destination = other / 'edited.bin'
        with self.assertRaises(SaveError):
            parser.save_as(self.doc, {'gold': 5}, destination)
        sidecar(other)
        with self.assertRaises(SaveError):
            parser.save_as(self.doc, {'gold': 5}, destination)
        (other / 'steam_autocloud.vdf').write_bytes(self.owner.raw)
        snapshot = parser.backup(self.doc)
        edited = parser.save_as(self.doc, {'gold': 5}, destination)
        self.assertEqual(parser.FIELDS[0].value(edited.payload), 5)
        self.assertEqual(self.source.read_bytes(), self.raw)
        restored = parser.restore(snapshot, other / 'restored.bin')
        self.assertEqual(restored.read_bytes(), self.raw)
        renamed = self.folder / 'renamed-context'
        renamed.mkdir()
        (renamed / 'STEAM_AUTOCLOUD.VDF').write_bytes(self.owner.raw)
        with self.assertRaises(SaveError):
            parser.restore(snapshot, renamed / 'restored.bin')
        binding = snapshot.with_name(snapshot.name + '.context.json')
        metadata = json.loads(binding.read_bytes())
        self.assertEqual(set(metadata), {'game_id', 'kind', 'context_sha256', 'owner_basename', 'save_sha256'})
        metadata['save_sha256'] = '0' * 64
        binding.write_text(json.dumps(metadata))
        with self.assertRaises(SaveError):
            parser.restore(snapshot, other / 'forged-restore.bin')
        self.assertFalse((other / 'forged-restore.bin').exists())

    def test_source_and_owner_races_leave_destination_unwritten(self):
        destination = self.folder / 'edited.bin'
        original_backup = parser.backup
        def race(document):
            result = original_backup(document)
            self.companion.write_bytes(self.owner.raw + b'\n')
            return result
        with patch.object(parser, 'backup', side_effect=race), self.assertRaises(SaveError):
            parser.save_as(self.doc, {'gold': 5}, destination)
        self.assertFalse(destination.exists())
        self.companion.write_bytes(self.owner.raw)
        def source_race(document):
            result = original_backup(document)
            self.source.write_bytes(self.raw[:-1] + bytes([self.raw[-1] ^ 1]))
            return result
        with patch.object(parser, 'backup', side_effect=source_race), self.assertRaises(SaveError):
            parser.save_as(self.doc, {'gold': 5}, destination)
        self.assertFalse(destination.exists())

    def test_destination_owner_race_damaged_manifest_and_cipher_verification(self):
        other = self.folder / 'destination'
        other.mkdir()
        companion = other / self.owner.basename
        companion.write_bytes(self.owner.raw)
        destination = other / 'edited.bin'
        original_backup = parser.backup
        def destination_race(document):
            snapshot = original_backup(document)
            companion.write_bytes(self.owner.raw + b'\n')
            return snapshot
        with patch.object(parser, 'backup', side_effect=destination_race), self.assertRaises(SaveError):
            parser.save_as(self.doc, {'gold': 5}, destination)
        self.assertFalse(destination.exists())
        companion.write_bytes(self.owner.raw)
        with patch.object(codec, 'encode_file', return_value=self.raw), self.assertRaises(SaveError):
            parser.serialize(self.doc, {'gold': 5})
        snapshot = parser.backup(self.doc)
        manifest = snapshot.with_suffix('.json')
        metadata = json.loads(manifest.read_bytes())
        metadata['game_id'] = 'samurai4dx'
        manifest.write_text(json.dumps(metadata))
        with self.assertRaises(SaveError):
            parser.restore(snapshot, other / 'restored.bin')
        self.assertFalse((other / 'restored.bin').exists())

    def test_copy_context_preserves_original_bytes_and_live_paths_reject(self):
        out = self.folder / 'selftest'
        parser.prepare_copy_context(self.doc, out)
        self.assertEqual((out / self.owner.basename).read_bytes(), self.owner.raw)
        (out / self.owner.basename).write_bytes(self.owner.raw + b'\n')
        with self.assertRaises(SaveError):
            parser.prepare_copy_context(self.doc, out)
        with self.assertRaises(SaveError):
            parser.read_save(self.folder / 'KoeiTecmo' / 'SAMURAI WARRIORS 5' / 'Savedata' / 'SAVEDATA00.BIN')

class Samurai5GenuineTests(unittest.TestCase):
    def native_copy(self, folder):
        source, owner = os.environ.get('SW5_PC_SAVE_COPY'), os.environ.get('SW5_PC_OWNER_COPY')
        if not source or not owner:
            self.skipTest('Set private SW5_PC_SAVE_COPY and SW5_PC_OWNER_COPY for genuine qualification.')
        target = folder / 'native-copy.bin'
        shutil.copyfile(source, target)
        shutil.copyfile(owner, folder / 'steam_autocloud.vdf')
        return target
    def test_genuine_cipher_roundtrip_surgical_edits_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = self.native_copy(folder)
            doc = parser.read_save(source)
            self.assertEqual(codec.encode_file(doc.payload, doc.owner.account_id,
                struct.unpack_from('<I', doc.raw, codec.SAVE_SIZE - 4)[0]), doc.raw)
            changes = {item.id: max(0, item.value(doc.payload) - 1) for item in parser.FIELDS}
            edited = parser.save_as(doc, changes, folder / 'edited.bin')
            expected = parser.changed_payload(doc, changes)
            self.assertEqual(edited.payload, expected)
            allowed = {offset for item in parser.FIELDS for offset in range(item.offset, item.offset + item.size)}
            touched = {i for i, (before, after) in enumerate(zip(doc.payload, edited.payload)) if before != after}
            self.assertTrue(touched)
            self.assertLessEqual(touched, allowed)
            self.assertEqual(source.read_bytes(), doc.raw)
            snapshot = parser.backup(doc)
            self.assertEqual(parser.restore(snapshot, folder / 'restored.bin').read_bytes(), doc.raw)
    def test_shared_private_copy_self_test_original_owner_context(self):
        from koei_editor.shared.verified_self_test import _run
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = self.native_copy(folder)
            original = parser.read_save(source)
            report = _run(BoundScalarAdapter(parser.GAME_ID, '.bin', parser), parser.GAME_ID, source, folder / 'validation')
            self.assertTrue(report['success'])
            self.assertEqual(report['fields_checked'], len(parser.fields_for(original)))
            self.assertEqual(report['integrity_kind'], 'none')
            self.assertFalse(report['checksum_verified'])
            self.assertFalse(report['in_game_load_tested'])
            self.assertEqual((folder / 'validation' / 'steam_autocloud.vdf').read_bytes(), original.owner.raw)
            self.assertNotIn(original.owner.raw, (folder / 'validation' / 'self-test-report.json').read_bytes())

    def test_gui_open_filter_stage_undo_review_inspect_save(self):
        import tkinter as tk
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest('Tk display unavailable.')
        self.addCleanup(root.destroy)
        from koei_editor.games.samurai5_pc.editor import Editor
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = self.native_copy(folder)
            original_raw = source.read_bytes()
            editor = Editor(root, parent=root)
            with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                editor.open()
            root.update()
            assert_paged_catalog(
                self, editor, (field.id for field in parser.fields_for(editor.document)))
            editor.search.set('Lumber')
            root.update()
            self.assertEqual(len(editor.fields.get_children()), 1)
            editor.search.set('')
            editor.stage_values({'gold': 10})
            self.assertEqual(editor.changes, {'gold': 10})
            editor.undo()
            self.assertEqual(editor.changes, {})
            editor.stage_values({'gold': 10})
            editor.review()
            editor.show_inspector()
            root.update()
            with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(folder / 'gui-edited.bin')):
                editor.save_as()
            self.assertEqual(parser.FIELDS[0].value(parser.read_save(folder / 'gui-edited.bin').payload), 10)
            self.assertEqual(source.read_bytes(), original_raw)

if __name__ == '__main__':
    unittest.main()
