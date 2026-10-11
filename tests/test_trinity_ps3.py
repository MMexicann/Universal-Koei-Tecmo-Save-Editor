"""Trinity procedural safety checks and optional genuine PS3 exports."""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.trinity_ps3 import parser
from koei_editor.shared.adapter_contract import BoundScalarAdapter


def fixture():
    raw = bytearray(parser.SAVE_SIZE)
    raw[16:] = bytes((i * 19 + 7) % 256 for i in range(parser.SAVE_SIZE - 16))
    raw[:len(parser.HEADER)] = parser.HEADER
    raw[0x58:0x5C] = (123456).to_bytes(4, 'big')
    return parser.seal(bytes(raw))


class TrinityPS3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = fixture()

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.source = self.folder / 'PLAY.DAT'
        self.source.write_bytes(self.raw)
        (self.folder / 'PARAM.SFO').write_bytes(parser.identity_metadata('BLUS30503-PLAY02'))
        self.document = parser.read_save(self.source)
        self.adapter = BoundScalarAdapter(parser.GAME_ID, '.dat', parser)

    def test_all_controls_surgical_full_tail_and_history_preservation(self):
        self.assertEqual(len(parser.fields_for(self.document)), 1)
        self.assertEqual(parser.serialize(self.document, {}), self.raw)
        for field in parser.fields_for(self.document):
            for value in (0, field.maximum // 2, field.maximum):
                changes = parser.stage(self.document, {}, field.id, value)
                output = parser.serialize(self.document, changes)
                parser.qualify(output)
                self.assertEqual(field.value(output), value)
                touched = {i for i, (a, b) in enumerate(zip(output, self.raw)) if a != b}
                self.assertLessEqual(touched, set(range(field.offset, field.offset + field.size)))
                self.assertEqual(output[field.offset + field.size:], self.raw[field.offset + field.size:])
                self.assertEqual(output[0x6C:0x70], self.raw[0x6C:0x70])
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_reduce_only_unstage_bulk_no_max_and_preserve_unusual_original(self):
        changes = parser.stage(self.document, {}, 'money', 100)
        self.assertEqual(len(parser.review(self.document, changes)), 1)
        self.assertEqual(parser.stage(self.document, changes, 'money', 123456), {})
        self.assertEqual(parser.maximums(self.document, changes), changes)
        self.assertEqual(parser.limit_values(self.document, changes, iter(changes)), {})
        for key, value in [('money', 123457), ('money', True), ('money', -1), ('exp', 0)]:
            with self.subTest(key=key, value=value), self.assertRaises(SaveError):
                parser.stage(self.document, {}, key, value)
        raw = bytearray(self.raw)
        raw[0x58:0x5C] = b'\xff' * 4
        document = parser.decode(parser.seal(bytes(raw)))
        self.assertEqual(parser.maximums(document, {}), {})
        self.assertEqual(parser.stage(document, {}, 'money', 0xFFFFFFFF), {})
        self.assertEqual(parser.serialize(document, {}), document.raw)

    def test_only_money_writable_inspection_and_external_integrity_distinction(self):
        self.assertEqual(tuple(parser.field_map(self.document)), ('money',))
        for key in ('lab_exp', 'licenses', 'skill_points', 'level'):
            with self.assertRaises(SaveError):
                parser.serialize(self.document, {key: 0})
        self.assertEqual(len(parser.inspection_rows(self.document)), 16)
        self.assertEqual(parser.INTEGRITY_KIND, 'external')
        self.assertFalse(parser.FORMAT.sample_verified)
        raw = bytearray(self.raw)
        raw[0x90000] ^= 1
        # This published writer does not claim nonexistent checksum detection.
        document = parser.decode(bytes(raw))
        self.assertEqual(parser.serialize(document, {}), bytes(raw))

    def test_malformed_framing_sizes_and_identity(self):
        for offset in (0, 4):
            raw = bytearray(self.raw)
            raw[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(SaveError):
                parser.decode(bytes(raw))
        for raw in (self.raw[:-1], self.raw + b'\0', bytearray(self.raw), self.raw * 2):
            with self.assertRaises(SaveError):
                parser.decode(raw)
        for directory in ('BLJM60212-PLAY02', 'BLES01184-PLAY02', 'NPEB02060-00', 'BLUS30503-PLAY020', 'BLUS30503-PLAYXX'):
            (self.folder / 'PARAM.SFO').write_bytes(parser.identity_metadata(directory))
            with self.assertRaises(SaveError):
                parser.read_save(self.source)
        (self.folder / 'PARAM.SFO').unlink()
        with self.assertRaises(SaveError):
            parser.read_save(self.source)

    def test_invalid_pending_and_forged_immutable_document(self):
        for changes in (None, [], {'money': '1'}, {None: 0}, {'money': -2}):
            with self.assertRaises(SaveError):
                parser.serialize(self.document, changes)
        for document in (replace(self.document, payload=bytearray(self.raw)),
                         replace(self.document, format=replace(parser.FORMAT, id='foreign')),
                         replace(self.document, native_directory='foreign'),
                         replace(self.document, source=None), replace(self.document, source=[])):
            with self.assertRaises(SaveError):
                parser.backup(document)

    def test_safe_storage_identity_backup_restore_and_source_guards(self):
        backup = parser.backup(self.document)
        self.assertTrue(backup.with_name(backup.name + '.context.json').exists())
        edited = parser.save_as(self.document, {'money': 456}, self.folder / 'edited.dat')
        self.assertEqual(parser.field_map(edited)['money'].value(edited.raw), 456)
        restored = parser.restore(backup, self.folder / 'restored.dat')
        self.assertEqual(restored.read_bytes(), self.raw)
        with self.assertRaises(FileExistsError):
            parser.save_as(self.document, {}, edited.source)
        with self.assertRaises(SaveError):
            parser.save_as(self.document, {}, self.folder / 'edited.bin')
        self.source.write_bytes(self.raw[:-1] + bytes([self.raw[-1] ^ 1]))
        for action in (lambda: parser.backup(self.document), lambda: parser.save_as(self.document, {}, self.folder / 'changed.dat')):
            with self.assertRaises(SaveError):
                action()
        self.assertFalse((self.folder / 'changed.dat').exists())

    def test_final_mid_serialize_source_and_identity_guard(self):
        original = parser.serialize
        def mutate(document, changes):
            output = original(document, changes)
            self.source.write_bytes(self.raw[:-1])
            return output
        with patch.object(parser, 'serialize', side_effect=mutate), self.assertRaises(SaveError):
            parser.save_as(self.document, {'money': 1}, self.folder / 'race.dat')
        self.assertFalse((self.folder / 'race.dat').exists())
        self.source.write_bytes(self.raw)
        original_backup = parser.backup
        def mutate_identity(document):
            result = original_backup(document)
            (self.folder / 'PARAM.SFO').write_bytes(parser.identity_metadata('BLES01184-PLAY02'))
            return result
        with patch.object(parser, 'backup', side_effect=mutate_identity), self.assertRaises(SaveError):
            parser.save_as(self.document, {}, self.folder / 'identity-race.dat')
        self.assertFalse((self.folder / 'identity-race.dat').exists())

    def test_shared_bound_selftest_original_context_and_damaged_restore(self):
        from koei_editor.shared.verified_self_test import _run
        metadata = parser.identity_metadata('BLUS30503-PLAY02')
        (self.folder / 'PARAM.SFO').write_bytes(metadata + b'PRIVATE-CONTEXT-SENTINEL')
        self.document = parser.read_save(self.source)
        report = _run(self.adapter, parser.GAME_ID, self.source, self.folder / 'selftest')
        self.assertTrue(report['success'])
        self.assertFalse(report['native_integrity_verified'])
        self.assertFalse(report['format_sample_verified'])
        self.assertEqual(report['integrity_kind'], 'external')
        self.assertFalse(report['in_game_load_tested'])
        self.assertEqual((self.folder / 'selftest' / 'PARAM.SFO').read_bytes(), metadata + b'PRIVATE-CONTEXT-SENTINEL')
        backup = parser.backup(self.document)
        from koei_editor.shared.copy_storage import snapshot_backup
        malformed = snapshot_backup(self.raw[:-1], self.source, parser.GAME_ID, self.folder / 'malformed')
        malformed.with_name(malformed.name + '.context.json').write_bytes(backup.with_name(backup.name + '.context.json').read_bytes())
        with self.assertRaises(SaveError):
            parser.restore(malformed, self.folder / 'damaged.dat')
        self.assertFalse((self.folder / 'damaged.dat').exists())
        backup.with_name(backup.name + '.context.json').write_bytes(b'{}')
        with self.assertRaises(SaveError):
            parser.restore(backup, self.folder / 'foreign.dat')

    def test_same_title_context_replacement_and_paired_backup_hash_rejected(self):
        backup = parser.backup(self.document)
        metadata = (self.folder / 'PARAM.SFO').read_bytes()
        (self.folder / 'PARAM.SFO').write_bytes(metadata + b'same-title-replacement')
        for action in (lambda: parser.backup(self.document),
                       lambda: parser.save_as(self.document, {}, self.folder / 'replacement.dat'),
                       lambda: parser.restore(backup, self.folder / 'replacement-restore.dat')):
            with self.assertRaises(SaveError):
                action()
        (self.folder / 'PARAM.SFO').write_bytes(metadata)
        from koei_editor.shared.copy_storage import snapshot_backup
        different = parser.serialize(self.document, {'money': 1})
        other = snapshot_backup(different, self.source, parser.GAME_ID, self.folder / 'other-backup')
        other.with_name(other.name + '.context.json').write_bytes(backup.with_name(backup.name + '.context.json').read_bytes())
        with self.assertRaises(SaveError):
            parser.restore(other, self.folder / 'mismatch.dat')
        for invalid in (None, [], 'unknown'):
            with self.assertRaises(SaveError):
                parser.field_hint(self.document, invalid)

    def test_optional_genuine_exports_each_control_surgery(self):
        corpus = os.environ.get('TRINITY_PS3_COPIES')
        if not corpus:
            self.skipTest('Private genuine decrypted US PS3 Trinity export directory not supplied.')
        sources = sorted(Path(corpus).glob('trinity-24026/BLUS30503-PLAY02/PLAY.DAT.decrypted'))
        self.assertGreaterEqual(len(sources), 1)
        identities = set()
        for source in sources:
            document = parser.decode(source.read_bytes(), source=source)
            identities.add(document.native_directory)
            self.assertEqual(parser.serialize(document, {}), document.raw)
            self.assertEqual(len(parser.fields_for(document)), 1)
            for field in parser.fields_for(document):
                output = parser.serialize(document, {field.id: field.value(document.raw) - 1})
                parser.qualify(output)
                touched = {i for i, (a, b) in enumerate(zip(output, document.raw)) if a != b}
                self.assertLessEqual(touched, set(range(field.offset, field.offset + field.size)))
                self.assertEqual(output[field.offset + field.size:], document.raw[field.offset + field.size:])
        self.assertEqual(identities, {'BLUS30503-PLAY02'})

    def test_actual_tk_search_edit_review_undo_max_backup_and_save(self):
        import tkinter as tk
        from koei_editor.games.trinity_ps3.editor import Editor
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.addCleanup(root.destroy)
        root.withdraw()
        editor = Editor(root)
        with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(self.source)):
            editor.open()
        self.assertIsNotNone(editor.document)
        editor.search.set('money')
        editor.refresh()
        self.assertEqual(len(editor.fields.get_children()), 1)
        editor.fields.selection_set('money')
        editor.value.set('500')
        editor.apply_selected()
        self.assertEqual(editor.changes, {'money': 500})
        editor.review()
        editor.undo()
        self.assertEqual(editor.changes, {})
        editor.max_visible()
        self.assertEqual(editor.changes, {})
        editor.stage_values({'money': 500})
        destination = self.folder / 'gui-edited.dat'
        editor.save_to(destination)
        self.assertEqual(parser.field_map(parser.read_save(destination))['money'].value(destination.read_bytes()), 500)
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertTrue(editor.backup.exists())
