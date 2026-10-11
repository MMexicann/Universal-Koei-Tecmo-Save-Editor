"""Procedural cipher/field checks and optional private genuine Ultimate/Tk runs."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.wo4 import codec as envelope
from koei_editor.games.wo4_ultimate import codec, parser
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from tests.scalar_contract import ScalarContractTests


def fixture():
    """Generated distinctive payloads, not an actual playable save."""
    blocks = []
    for index, offset, size, payload_size in envelope.SPECS:
        payload = bytearray((i * 11 + 29) % 256 for i in range(payload_size))
        if index == 1:
            struct.pack_into('<III', payload, 0, codec.REVISION, 0, 0)
            payload[-codec.SYSTEM_RESERVED_SIZE:] = bytes(codec.SYSTEM_RESERVED_SIZE)
            for _, _, at, width, _ in parser.RESOURCE_MAP:
                payload[at:at + width] = (37).to_bytes(width, 'little')
            for identity in range(parser.ELEMENT_COUNT):
                struct.pack_into('<H', payload, parser.ELEMENT_BASE + identity * 2, 0)
            struct.pack_into('<H', payload, parser.ELEMENT_BASE + 2, 17)
            struct.pack_into('<H', payload, 0x30E, 20)
        else:
            payload[-codec.PLAY_RESERVED_SIZE:] = bytes(codec.PLAY_RESERVED_SIZE)
            for record in range(parser.OFFICER_COUNT):
                base = record * parser.OFFICER_STRIDE
                struct.pack_into('<I', payload, base, 0)
                payload[base + parser.PROMOTIONS_RELATIVE] = 0
            struct.pack_into('<I', payload, 0, 999)
            struct.pack_into('<H', payload, parser.SKILL_POINTS_RELATIVE, 71)
            payload[parser.PROMOTIONS_RELATIVE] = 1
            struct.pack_into('<H', payload, parser.UPGRADE_STONES_RELATIVE, 81)
            for record in range(parser.WEAPON_COUNT):
                struct.pack_into('<H', payload, parser.WEAPON_BASE + record * parser.WEAPON_STRIDE, 0xFFFF)
        padding = bytes((i + 93) % 256 for i in range(size - 4 - 16 - payload_size))
        blocks.append(envelope.Block(index, offset, 0x20304050 + index, bytes(payload), padding))
    return envelope.encode(tuple(blocks))


def mutate(raw, offset, data):
    blocks = envelope.decode(raw)
    payload = bytearray(b''.join(b.payload for b in blocks))
    payload[offset:offset + len(data)] = data
    return envelope.encode((replace(blocks[0], payload=bytes(payload[:codec.SYSTEM_PAYLOAD_SIZE])),
                            replace(blocks[1], payload=bytes(payload[codec.SYSTEM_PAYLOAD_SIZE:]))))


def native_paths():
    return [p for item in os.environ.get('WO4U_SAVE_COPIES', '').split(os.pathsep) if item
            for p in ([Path(item)] if Path(item).is_file() else Path(item).rglob('*.BIN'))]


class UltimateContractTests(ScalarContractTests, unittest.TestCase):
    game_id = parser.GAME_ID

    def fixture_bytes(self):
        return fixture()

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.game = SimpleNamespace(extension='.bin')
        self.adapter = BoundScalarAdapter(parser.GAME_ID, '.bin', parser)
        self.raw = fixture()
        self.source = self.folder / 'generated.bin'
        self.source.write_bytes(self.raw)
        self.document = self.adapter.read_save(self.source)


class UltimateFormatTests(unittest.TestCase):
    def surgical(self, document, field):
        value = field.minimum if field.value(document.payload) != field.minimum else field.maximum
        pending = parser.stage(document, {}, field.id, value)
        reopened = parser.decode(parser.serialize(document, pending))
        allowed = set(range(field.offset, field.offset + field.size))
        touched = {i for i, (a, b) in enumerate(zip(document.payload, reopened.payload)) if a != b}
        self.assertTrue(touched)
        self.assertLessEqual(touched, allowed)
        self.assertEqual(field.value(reopened.payload), value)
        original_blocks, edited_blocks = envelope.decode(document.raw), envelope.decode(reopened.raw)
        for first, second in zip(original_blocks, edited_blocks):
            self.assertEqual(first.iv_seed, second.iv_seed)
            self.assertEqual(first.padding, second.padding)
        self.assertEqual(parser.stage(document, pending, field.id, field.value(document.payload)), {})

    def test_procedural_noop_all_fields_surgical_seeds_padding_and_unstage(self):
        raw = fixture()
        document = parser.decode(raw)
        self.assertEqual(parser.serialize(document, {}), raw)
        self.assertEqual(len(parser.fields_for(document)), 7)
        for field in parser.fields_for(document):
            self.surgical(document, field)
        self.assertEqual(document.raw, raw)
        original = parser.decode(raw).payload
        edited = parser.decode(parser.serialize(document, {'officer_0_upgrade_stones': 9999})).payload
        base = codec.SYSTEM_PAYLOAD_SIZE
        self.assertEqual(edited[base + 0x112:base + 0x120], original[base + 0x112:base + 0x120])

    def test_foreign_revision_lengths_fingerprints_reserved_regions_and_types(self):
        raw = fixture()
        for bad in (raw[:-1], raw + b'\0', bytes(len(raw)), bytearray(raw), memoryview(raw)):
            with self.assertRaises(SaveError):
                parser.decode(bad)
        for offset in (envelope.SYSTEM_BLOCK_SIZE - 8, len(raw) - 8):
            damaged = bytearray(raw)
            damaged[offset] ^= 1
            with self.assertRaises(SaveError):
                parser.decode(bytes(damaged))
        for offset, data in ((0, struct.pack('<I', 20180720)),
                             (4, struct.pack('<I', 1)), (8, struct.pack('<I', 1)),
                             (codec.SYSTEM_PAYLOAD_SIZE - 1, b'\1'),
                             (codec.PAYLOAD_SIZE - 1, b'\1')):
            with self.assertRaises(SaveError):
                parser.decode(mutate(raw, offset, data))
        with self.assertRaises(SaveError):
            parser.decode(raw, 'wo4')
        with self.assertRaises(SaveError):
            codec.decode(bytearray(raw))

    def test_unusual_zero_unknown_and_progression_values_preserved(self):
        raw = fixture()
        raw = mutate(raw, 0x274, struct.pack('<I', 0xFFFFFFFF))
        raw = mutate(raw, parser.ELEMENT_BASE + 4, struct.pack('<H', 65535))
        raw = mutate(raw, codec.SYSTEM_PAYLOAD_SIZE + parser.OFFICER_STRIDE, struct.pack('<I', 0xFFFFFFFF))
        raw = mutate(raw, codec.SYSTEM_PAYLOAD_SIZE + parser.SKILL_POINTS_RELATIVE, struct.pack('<H', 65535))
        document = parser.decode(raw)
        mapping = parser.field_map(document)
        self.assertNotIn('element_2', mapping)
        self.assertNotIn('officer_1_skill_points', mapping)
        self.assertNotIn('gems', parser.maximums(document, {}))
        self.assertNotIn('gems', parser.maximums(document, {'gems': 100}))
        self.assertNotIn('officer_0_skill_points', parser.maximums(document, {'officer_0_skill_points': 10}))
        self.assertNotIn('officer_0_skill_points', parser.maximums(document, {}))
        pending = parser.stage(document, {}, 'gems', 20)
        self.assertEqual(parser.stage(document, pending, 'gems', 0xFFFFFFFF), {})
        edited = parser.decode(parser.serialize(document, {'crystals': 0}))
        self.assertEqual(edited.payload[parser.ELEMENT_BASE + 4:parser.ELEMENT_BASE + 6], b'\xff\xff')
        self.assertEqual(edited.payload[codec.SYSTEM_PAYLOAD_SIZE:], document.payload[codec.SYSTEM_PAYLOAD_SIZE:])

    def test_natural_max_bounds_no_new_inventory_or_story_grants(self):
        document = parser.decode(fixture())
        pending = parser.maximums(document, {})
        edited = parser.decode(parser.serialize(document, pending))
        for field in parser.fields_for(document):
            self.assertEqual(field.value(edited.payload), field.maximum)
            for value in (-1, field.maximum + 1, True, 2.5, '2'):
                with self.assertRaises(SaveError):
                    parser.stage(document, {}, field.id, value)
        for key in ('element_0', 'element_2', 'officer_1_skill_points', [], None):
            with self.assertRaises(SaveError):
                parser.stage(document, {}, key, 1)
            with self.assertRaises(SaveError):
                parser.limit_values(document, {}, [key])
        self.assertEqual(parser.limit_values(document, {}, iter(['crystals'])), {'crystals': 999})
        self.assertNotIn('skill_orbs', pending)
        with self.assertRaises(SaveError):
            parser.stage(document, {}, 'skill_orbs', 21)
        self.assertEqual(edited.payload[0x30E:0x310], document.payload[0x30E:0x310])
        self.assertEqual(edited.payload[0x278:0x27C], document.payload[0x278:0x27C])
        self.assertEqual(edited.payload[0x27E:0x280], document.payload[0x27E:0x280])
        self.assertEqual(edited.payload[codec.SYSTEM_PAYLOAD_SIZE + parser.PROMOTIONS_RELATIVE],
                         document.payload[codec.SYSTEM_PAYLOAD_SIZE + parser.PROMOTIONS_RELATIVE])

    def test_snapshot_source_backup_restore_and_race_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / 'copy.bin'
            raw = fixture()
            source.write_bytes(raw)
            document = parser.read_save(source)
            for bad in (replace(document, payload=bytes(len(document.payload))),
                        replace(document, raw=bytes(len(raw)))):
                with self.assertRaises(SaveError):
                    parser.serialize(bad, {})
            with self.assertRaises(FileExistsError):
                parser.save_as(document, {}, source)
            backup = parser.backup(document)
            restored = folder / 'restored.bin'
            parser.restore(backup, restored)
            self.assertEqual(restored.read_bytes(), raw)
            damaged = mutate(raw, codec.PAYLOAD_SIZE - 1, b'\1')
            backup.write_bytes(damaged)
            manifest_path = backup.with_suffix('.json')
            manifest = json.loads(manifest_path.read_text())
            manifest['sha256'] = hashlib.sha256(damaged).hexdigest()
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaises(SaveError):
                parser.restore(backup, folder / 'corrupt-restored.bin')
            self.assertFalse((folder / 'corrupt-restored.bin').exists())
            backup = parser.backup(document)
            source.write_bytes(raw[:-1])
            with self.assertRaises(SaveError):
                parser.save_as(document, {}, folder / 'stale.bin')
            source.write_bytes(raw)
            original = parser.backup
            def change_after_backup(doc):
                result = original(doc)
                source.write_bytes(raw[:-1])
                return result
            with patch.object(parser, 'backup', side_effect=change_after_backup):
                with self.assertRaises(SaveError):
                    parser.save_as(document, {}, folder / 'race.bin')
            self.assertFalse((folder / 'race.bin').exists())
            source.write_bytes(raw)
            live = folder / 'KoeiTecmo' / 'Warriors Orochi 4' / 'arbitrary.bin'
            live.parent.mkdir(parents=True)
            live.write_bytes(raw)
            for action in (lambda: parser.read_save(live),
                           lambda: parser.save_as(document, {}, live.parent / 'new.bin'),
                           lambda: parser.restore(backup, live.parent / 'restore.bin')):
                with self.assertRaises(SaveError):
                    action()
            alias = folder / 'alias'
            alias.symlink_to(live.parent, target_is_directory=True)
            with self.assertRaises(SaveError):
                parser.read_save(alias / 'arbitrary.bin')
            source.unlink()
            with self.assertRaises(SaveError):
                parser.backup(document)

    def test_genuine_native_roundtrip_every_field_surgical_and_inspectors(self):
        paths = native_paths()
        if not paths:
            self.skipTest('Private genuine Ultimate copies were not supplied.')
        for path in paths:
            raw = path.read_bytes()
            document = parser.decode(raw)
            self.assertEqual(parser.serialize(document, {}), raw)
            self.assertGreater(len(parser.fields_for(document)), 50)
            self.assertEqual(len(parser.element_records(document)), 64)
            self.assertTrue(parser.officer_records(document))
            self.assertTrue(parser.weapon_records(document))
            for field in parser.fields_for(document):
                self.surgical(document, field)

    def test_actual_tk_native_open_stage_review_undo_save_as_and_restore(self):
        paths = native_paths()
        if not paths:
            self.skipTest('Private genuine Ultimate copies were not supplied.')
        import tkinter as tk
        from koei_editor.games.wo4_ultimate.editor import Editor
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(str(error))
        self.addCleanup(root.destroy)
        root.withdraw()
        error_dialog = patch('koei_editor.shared.verified_gui.messagebox.showerror', side_effect=AssertionError('Unexpected GUI error'))
        error_dialog.start()
        self.addCleanup(error_dialog.stop)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / 'native-copy.bin'
            source.write_bytes(paths[0].read_bytes())
            editor = Editor(root, parent=root)
            with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                editor.open()
            root.update()
            self.assertEqual(editor.document.raw, source.read_bytes())
            field = parser.fields_for(editor.document)[0]
            editor.stage_values({field.id: max(0, field.value(editor.document.payload) - 1)})
            self.assertTrue(editor.changes)
            editor.review()
            root.update()
            self.assertTrue(any(isinstance(child, tk.Toplevel) for child in root.winfo_children()))
            editor.undo()
            self.assertFalse(editor.changes)
            editor.stage_values({field.id: max(0, field.value(editor.document.payload) - 1)})
            destination = folder / 'edited.bin'
            with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(destination)):
                editor.save_as()
            self.assertTrue(destination.exists())
            self.assertNotEqual(destination.read_bytes(), source.read_bytes())
            reopened = parser.read_save(destination)
            self.assertEqual(field.value(reopened.payload), field.value(parser.read_save(source).payload) - 1)
            backups = list((folder / 'UniversalEditorBackups').glob('*.bin'))
            self.assertTrue(backups)
            parser.restore(backups[0], folder / 'restored.bin')
            self.assertEqual((folder / 'restored.bin').read_bytes(), source.read_bytes())
