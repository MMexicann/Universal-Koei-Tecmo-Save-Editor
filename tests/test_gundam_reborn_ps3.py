"""Reborn procedural safety checks and optional genuine PS3 exports."""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.gundam_reborn_ps3 import parser
from koei_editor.shared.adapter_contract import BoundScalarAdapter


def fixture():
    raw = bytearray(parser.SAVE_SIZE)
    raw[16:] = bytes((i * 19 + 7) % 256 for i in range(parser.SAVE_SIZE - 16))
    raw[:12] = bytes.fromhex('00000000000000020005f938')
    raw[0x5AD44:0x5AD48] = (123456).to_bytes(4, 'big')
    for _, _, offset in parser.PILOTS:
        raw[offset] = 29
        raw[offset + 2:offset + 6] = (12345).to_bytes(4, 'big')
        raw[offset + 26:offset + 30] = (700).to_bytes(4, 'big')
    return parser.seal(bytes(raw))


class RebornPS3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = fixture()

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.source = self.folder / 'DATA.BIN'
        self.source.write_bytes(self.raw)
        (self.folder / 'PARAM.SFO').write_bytes(parser.identity_metadata('NPEB02060-00'))
        self.document = parser.read_save(self.source)
        self.adapter = BoundScalarAdapter(parser.GAME_ID, '.bin', parser)

    def test_all_controls_surgical_full_tail_and_history_preservation(self):
        self.assertEqual(len(parser.fields_for(self.document)), 3)
        self.assertEqual(parser.serialize(self.document, {}), self.raw)
        for field in parser.fields_for(self.document):
            for value in (0, field.maximum // 2, field.maximum):
                changes = parser.stage(self.document, {}, field.id, value)
                output = parser.serialize(self.document, changes)
                parser.qualify(output)
                self.assertEqual(field.value(output), value)
                touched = {i for i, (a, b) in enumerate(zip(output, self.raw)) if a != b}
                self.assertLessEqual(touched, set(range(12, 16)) | set(range(field.offset, field.offset + field.size)))
                self.assertEqual(output[parser.CONTENT_END:], self.raw[parser.CONTENT_END:])
                self.assertEqual(output[0x57F90:0x57F94], self.raw[0x57F90:0x57F94])
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_reduce_only_unstage_bulk_no_max_and_preserve_unusual_original(self):
        changes = parser.stage(self.document, {}, 'money', 100)
        changes = parser.stage(self.document, changes, 'amuro_team_points', 600)
        self.assertEqual(len(parser.review(self.document, changes)), 2)
        self.assertEqual(parser.stage(self.document, changes, 'money', 123456), {'amuro_team_points': 600})
        self.assertEqual(parser.maximums(self.document, changes), changes)
        self.assertEqual(parser.limit_values(self.document, changes, iter(changes)), {})
        for key, value in [('money', 123457), ('amuro_team_points', 701), ('money', True), ('money', -1), ('exp', 0)]:
            with self.subTest(key=key, value=value), self.assertRaises(SaveError):
                parser.stage(self.document, {}, key, value)
        raw = bytearray(self.raw)
        raw[0x5AD44:0x5AD48] = b'\xff' * 4
        document = parser.decode(parser.seal(bytes(raw)))
        self.assertEqual(parser.maximums(document, {}), {})
        self.assertEqual(parser.stage(document, {}, 'money', 0xFFFFFFFF), {})
        self.assertEqual(parser.serialize(document, {}), document.raw)

    def test_existing_pilot_qualification_unknown_material_and_progression_immutable(self):
        raw = bytearray(self.raw)
        raw[parser.PILOTS[0][2]] = 99
        offset = parser.PILOTS[1][2]
        raw[offset + 2:offset + 6] = bytes(4)
        document = parser.decode(parser.seal(bytes(raw)))
        self.assertEqual(tuple(parser.field_map(document)), ('money',))
        for key in ('amuro_team_points', 'kamille_team_points', 'materials_1', 'lifetime_money', 'level'):
            with self.assertRaises(SaveError):
                parser.serialize(document, {key: 0})
        rows = parser.inspection_rows(self.document)
        self.assertEqual(sum(r['group'] == 'Material storage' for r in rows), 10)
        self.assertTrue(any('Pilot EXP' in r['value'] for r in rows))

    def test_malformed_checksum_framing_sizes_and_identity(self):
        for offset in (12, 16, 0x5AD44, parser.CONTENT_END - 1):
            raw = bytearray(self.raw)
            raw[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(SaveError):
                parser.decode(bytes(raw))
        for offset in (0, 4, 8):
            raw = bytearray(self.raw)
            raw[offset] ^= 1
            with self.assertRaises(SaveError):
                parser.decode(parser.seal(bytes(raw)))
        for raw in (self.raw[:-1], self.raw + b'\0', bytearray(self.raw), self.raw * 2):
            with self.assertRaises(SaveError):
                parser.decode(raw)
        for directory in ('NPUB31531-00', 'BLUS30703-00', 'NPEB02060-000', 'NPEB02060-XX'):
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
        edited = parser.save_as(self.document, {'money': 456}, self.folder / 'edited.bin')
        self.assertEqual(parser.field_map(edited)['money'].value(edited.raw), 456)
        restored = parser.restore(backup, self.folder / 'restored.bin')
        self.assertEqual(restored.read_bytes(), self.raw)
        with self.assertRaises(FileExistsError):
            parser.save_as(self.document, {}, edited.source)
        with self.assertRaises(SaveError):
            parser.save_as(self.document, {}, self.folder / 'edited.dat')
        self.source.write_bytes(self.raw[:-1] + bytes([self.raw[-1] ^ 1]))
        for action in (lambda: parser.backup(self.document), lambda: parser.save_as(self.document, {}, self.folder / 'changed.bin')):
            with self.assertRaises(SaveError):
                action()
        self.assertFalse((self.folder / 'changed.bin').exists())

    def test_final_mid_serialize_source_and_identity_guard(self):
        original = parser.serialize
        def mutate(document, changes):
            output = original(document, changes)
            self.source.write_bytes(self.raw[:-1])
            return output
        with patch.object(parser, 'serialize', side_effect=mutate), self.assertRaises(SaveError):
            parser.save_as(self.document, {'money': 1}, self.folder / 'race.bin')
        self.assertFalse((self.folder / 'race.bin').exists())
        self.source.write_bytes(self.raw)
        original_backup = parser.backup
        def mutate_identity(document):
            result = original_backup(document)
            (self.folder / 'PARAM.SFO').write_bytes(parser.identity_metadata('NPJB00533-00'))
            return result
        with patch.object(parser, 'backup', side_effect=mutate_identity), self.assertRaises(SaveError):
            parser.save_as(self.document, {}, self.folder / 'identity-race.bin')
        self.assertFalse((self.folder / 'identity-race.bin').exists())

    def test_shared_bound_selftest_identity_only_and_damaged_restore(self):
        from koei_editor.shared.verified_self_test import _run
        metadata = parser.identity_metadata('NPEB02060-00')
        (self.folder / 'PARAM.SFO').write_bytes(metadata + b'PRIVATE-CONTEXT-SENTINEL')
        self.document = parser.read_save(self.source)
        report = _run(self.adapter, parser.GAME_ID, self.source, self.folder / 'selftest')
        self.assertTrue(report['success'])
        self.assertTrue(report['native_integrity_verified'])
        self.assertFalse(report['in_game_load_tested'])
        self.assertEqual((self.folder / 'selftest' / 'PARAM.SFO').read_bytes(), metadata + b'PRIVATE-CONTEXT-SENTINEL')
        backup = parser.backup(self.document)
        from koei_editor.shared.copy_storage import snapshot_backup
        malformed = snapshot_backup(self.raw[:-1], self.source, parser.GAME_ID, self.folder / 'malformed')
        malformed.with_name(malformed.name + '.context.json').write_bytes(backup.with_name(backup.name + '.context.json').read_bytes())
        with self.assertRaises(SaveError):
            parser.restore(malformed, self.folder / 'damaged.bin')
        self.assertFalse((self.folder / 'damaged.bin').exists())
        backup.with_name(backup.name + '.context.json').write_bytes(b'{}')
        with self.assertRaises(SaveError):
            parser.restore(backup, self.folder / 'foreign.bin')

    def test_same_title_context_replacement_and_paired_backup_hash_rejected(self):
        backup = parser.backup(self.document)
        metadata = (self.folder / 'PARAM.SFO').read_bytes()
        (self.folder / 'PARAM.SFO').write_bytes(metadata + b'same-title-replacement')
        for action in (lambda: parser.backup(self.document),
                       lambda: parser.save_as(self.document, {}, self.folder / 'replacement.bin'),
                       lambda: parser.restore(backup, self.folder / 'replacement-restore.bin')):
            with self.assertRaises(SaveError):
                action()
        (self.folder / 'PARAM.SFO').write_bytes(metadata)
        from koei_editor.shared.copy_storage import snapshot_backup
        different = parser.serialize(self.document, {'money': 1})
        other = snapshot_backup(different, self.source, parser.GAME_ID, self.folder / 'other-backup')
        other.with_name(other.name + '.context.json').write_bytes(backup.with_name(backup.name + '.context.json').read_bytes())
        with self.assertRaises(SaveError):
            parser.restore(other, self.folder / 'mismatch.bin')
        for invalid in (None, [], 'unknown'):
            with self.assertRaises(SaveError):
                parser.field_hint(self.document, invalid)

    def test_optional_genuine_exports_each_control_surgery(self):
        corpus = os.environ.get('GUNDAM_REBORN_PS3_COPIES')
        if not corpus:
            self.skipTest('Private genuine decrypted PS3 Reborn export directory not supplied.')
        sources = sorted(Path(corpus).glob('dynasty-warriors-gundam-reborn-*/**/DATA.BIN.decrypted'))
        self.assertGreaterEqual(len(sources), 3)
        identities = set()
        for source in sources:
            document = parser.decode(source.read_bytes(), source=source)
            identities.add(document.native_directory)
            self.assertEqual(parser.serialize(document, {}), document.raw)
            self.assertEqual(len(parser.fields_for(document)), 3)
            for field in parser.fields_for(document):
                output = parser.serialize(document, {field.id: field.value(document.raw) - 1})
                parser.qualify(output)
                touched = {i for i, (a, b) in enumerate(zip(output, document.raw)) if a != b}
                self.assertLessEqual(touched, set(range(12, 16)) | set(range(field.offset, field.offset + field.size)))
                self.assertEqual(output[parser.CONTENT_END:], document.raw[parser.CONTENT_END:])
        self.assertEqual(identities, {'NPEB02060-00', 'NPJB00533-00'})

    def test_actual_tk_search_edit_review_undo_max_backup_and_save(self):
        import tkinter as tk
        from koei_editor.games.gundam_reborn_ps3.editor import Editor
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
        editor.search.set('Amuro')
        editor.refresh()
        self.assertEqual(len(editor.fields.get_children()), 1)
        editor.fields.selection_set('amuro_team_points')
        editor.value.set('500')
        editor.apply_selected()
        self.assertEqual(editor.changes, {'amuro_team_points': 500})
        editor.review()
        editor.undo()
        self.assertEqual(editor.changes, {})
        editor.max_visible()
        self.assertEqual(editor.changes, {})
        editor.stage_values({'amuro_team_points': 500})
        destination = self.folder / 'gui-edited.bin'
        editor.save_to(destination)
        self.assertEqual(parser.field_map(parser.read_save(destination))['amuro_team_points'].value(destination.read_bytes()), 500)
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertTrue(editor.backup.exists())
