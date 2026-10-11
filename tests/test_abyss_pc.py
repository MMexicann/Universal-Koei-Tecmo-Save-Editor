"""Native-slot qualification plus explicitly procedural adversarial checks.

Private ABYSS_NATIVE_COPY_DIRECTORY contains complete gameplay/system copies
and their original steam_autocloud.vdf. No player data is distributed.
"""
from dataclasses import replace
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.abyss_pc import parser
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw3.save_codec import CNG_AES
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from koei_editor.shared.steam_owner import read_owner

# A made-up procedural account, never derived from a player fixture.
PROCEDURAL_VDF = b'"steam_autocloud.vdf"\n{\n"accountid" "12345"\n}\n'


def procedural(directory, value=321, revision=0xA4):
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / 'GAMEDATA00.BIN'
    (directory / 'steam_autocloud.vdf').write_bytes(PROCEDURAL_VDF)
    owner = read_owner(source)
    body = bytearray((index * 53 + 71) & 255 for index in range(parser.SAVE_SIZE - 32))
    struct.pack_into('<I', body, 0, revision)
    struct.pack_into('<I', body, 6, value)
    with CNG_AES('CBC') as provider:
        raw = parser.OUTER_MAGIC + provider.transform(parser.INNER_MAGIC + bytes(body),
                                                      parser._key(owner), direction='encrypt', iv=parser.IV)
    source.write_bytes(raw)
    return source


def native_source():
    setting = os.environ.get('ABYSS_NATIVE_COPY_DIRECTORY')
    return Path(setting) / 'GAMEDATA00.BIN' if setting else None


class AbyssPcTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.source = procedural(self.folder)
        self.document = parser.read_save(self.source)

    def assert_surgical(self, original, edited):
        self.assertNotEqual(edited.payload, original.payload)
        self.assertEqual(original.payload[:6], edited.payload[:6])
        self.assertEqual(original.payload[10:], edited.payload[10:])
        self.assertEqual(original.raw[:16], edited.raw[:16])
        self.assertEqual(len(original.raw), len(edited.raw))

    def test_procedural_noop_wallet_only_and_full_unknown_preservation(self):
        document = self.document
        self.assertEqual(parser.serialize(document, {}), document.raw)
        changes = parser.stage(document, {}, 'karma_embers', 654)
        edited = parser.decode(parser.serialize(document, changes), source=document.source)
        self.assert_surgical(document, edited)
        self.assertEqual(parser.KARMA.value(edited.payload), 654)
        self.assertEqual(parser.review(document, changes)[0][1:], (321, 654))
        self.assertEqual(parser.stage(document, changes, 'karma_embers', 321), {})
        self.assertEqual(parser.maximums(document, {})['karma_embers'], 9_999_999)
        self.assertEqual(len(parser.recruitment_records(document)), 829)
        self.assertEqual(parser.recruitment_records(document), parser.recruitment_records(edited))
        self.assertEqual(parser.SERIALIZED_EXTENT, 0x26FE0)

    def test_preserve_higher_originals_during_max_and_unstage(self):
        source = procedural(self.folder, 0xFFFFFFFF)
        document = parser.read_save(source)
        self.assertEqual(parser.maximums(document, {}), {})
        self.assertEqual(parser.limit_values(document, {}, ['karma_embers']), {'karma_embers': 0xFFFFFFFF})
        changes = parser.stage(document, {}, 'karma_embers', 10)
        self.assertEqual(parser.maximums(document, changes), {})
        self.assertEqual(parser.stage(document, changes, 'karma_embers', 0xFFFFFFFF), {})
        self.assertEqual(parser.serialize(document, {}), document.raw)
        with self.assertRaises(SaveError):
            parser.stage(document, {}, 'karma_embers', 9_999_999 + 1)

    def test_malformed_envelope_context_snapshot_and_fields(self):
        document = self.document
        for raw in (document.raw[:-1], document.raw + b'\0', bytearray(document.raw),
                    b'X' + document.raw[1:], document.raw[:0x2800]):
            with self.assertRaises(SaveError):
                parser._decode_with_owner(raw, document.owner)
        other = self.folder / 'other'
        procedural(other)
        (other / 'steam_autocloud.vdf').write_bytes(PROCEDURAL_VDF.replace(b'12345', b'54321'))
        with self.assertRaises(SaveError):
            parser.decode(document.raw, source=other / 'GAMEDATA00.BIN')
        for revision in (0x77, 0xA3, 0xA5, 0x10000A4):
            with self.assertRaises(SaveError):
                parser.read_save(procedural(self.folder / f'rev-{revision:x}', revision=revision))
        for forged in (replace(document, raw=bytearray(document.raw)),
                       replace(document, payload=bytearray(document.payload)),
                       replace(document, payload=document.payload[:-1]),
                       replace(document, payload=document.payload[:600] + b'X' + document.payload[601:])):
            with self.assertRaises(SaveError):
                parser.serialize(forged, {})
        for value in (-1, 10_000_000, True, 1.0, '1', None):
            with self.assertRaises(SaveError):
                parser.stage(document, {}, 'karma_embers', value)
        for key in ('hero_1', None, [], {}):
            with self.assertRaises(SaveError):
                parser.stage(document, {}, key, 1)
        self.assertNotIn(str(document.owner.account_id), repr(document))
        self.assertNotIn(str(document.owner.steam_id64), repr(document))
        self.assertNotIn('payload=', repr(document))

    def test_backup_save_restore_bindings_and_original_preservation(self):
        document = self.document
        backup = parser.backup(document)
        metadata = json.loads(backup.with_name(backup.name + '.context.json').read_bytes())
        self.assertEqual(set(metadata), {'game_id', 'kind', 'owner_sha256', 'owner_basename', 'native_sha256'})
        self.assertNotIn('account', json.dumps(metadata))
        edited = parser.save_as(document, {'karma_embers': 123}, self.folder / 'edited.bin')
        self.assert_surgical(document, edited)
        self.assertEqual(self.source.read_bytes(), document.raw)
        restored = parser.restore(backup, self.folder / 'restored.bin')
        self.assertEqual(restored.read_bytes(), document.raw)
        for destination in (self.source, edited.source):
            with self.assertRaises(FileExistsError):
                parser.save_as(document, {}, destination)
        unknown = self.folder / 'unknown'
        unknown.mkdir()
        with self.assertRaises(SaveError):
            parser.save_as(document, {}, unknown / 'edited.bin')
        metadata['owner_sha256'] = '0' * 64
        backup.with_name(backup.name + '.context.json').write_text(json.dumps(metadata))
        with self.assertRaises(SaveError):
            parser.restore(backup, self.folder / 'bad-restore.bin')

    def test_changed_source_and_owner_before_and_after_backup(self):
        document = self.document
        self.source.write_bytes(document.raw[:-1])
        with self.assertRaises(SaveError):
            parser.backup(document)
        self.source.write_bytes(document.raw)
        original_backup = parser.backup
        def swap_owner(value):
            result = original_backup(value)
            (self.folder / 'steam_autocloud.vdf').write_bytes(PROCEDURAL_VDF + b'\n')
            return result
        destination = self.folder / 'raced.bin'
        with patch.object(parser, 'backup', side_effect=swap_owner):
            with self.assertRaises(SaveError):
                parser.save_as(document, {'karma_embers': 10}, destination)
        self.assertFalse(destination.exists())
        self.assertEqual(self.source.read_bytes(), document.raw)

    def test_deleted_source_is_rejected_without_private_path_in_error(self):
        self.source.unlink()
        for operation in (lambda: parser.backup(self.document),
                          lambda: parser.save_as(self.document, {}, self.folder / 'deleted.bin'),
                          lambda: parser.read_save(self.source)):
            with self.assertRaises(SaveError) as error:
                operation()
            self.assertNotIn(str(self.folder), str(error.exception))

    def test_live_paths_symlink_aliases_and_hardlinks_rejected(self):
        live = self.folder / 'Documents' / 'KoeiTecmo' / 'WARRIORSAbyss' / 'SAVEDATA'
        live_source = procedural(live)
        with self.assertRaises(SaveError):
            parser.read_save(live_source)
        alias = self.folder / 'alias'
        try:
            alias.symlink_to(live, target_is_directory=True)
        except OSError:
            alias = None
        if alias is not None:
            with self.assertRaises(SaveError):
                parser.read_save(alias / 'GAMEDATA00.BIN')
        linked = self.folder / 'hardlink.bin'
        try:
            os.link(self.source, linked)
        except OSError:
            linked = None
        if linked is not None:
            with self.assertRaises(SaveError):
                parser.read_save(linked)
        with self.assertRaises(SaveError):
            parser.prepare_copy_context(self.document, live)

    def test_private_self_test_context_copy_and_contract(self):
        from koei_editor.shared.verified_self_test import _run
        output = self.folder / 'private-test'
        backend = BoundScalarAdapter(parser.GAME_ID, parser.EXTENSION, parser)
        report = _run(backend, parser.GAME_ID, self.source, output)
        self.assertTrue(report['success'])
        self.assertEqual(report['fields_changed'], 1)
        self.assertEqual(report['integrity_kind'], 'none')
        self.assertFalse(report['checksum_verified'])
        self.assertFalse(report['in_game_load_tested'])
        self.assertEqual((output / 'steam_autocloud.vdf').read_bytes(), PROCEDURAL_VDF)

    def test_bound_scalar_full_workflow_and_iterable_max(self):
        adapter = BoundScalarAdapter(parser.GAME_ID, parser.EXTENSION, parser)
        document = adapter.read_save(self.source)
        decoded = adapter.decode(document.raw, source=self.source)
        self.assertEqual(decoded.payload, document.payload)
        pending = adapter.stage(document, {}, 'karma_embers', 654)
        self.assertEqual(adapter.limit_values(document, pending, iter(['karma_embers'])),
                         {'karma_embers': 9_999_999})
        self.assertEqual(parser.limit_values(document, pending, iter(['karma_embers'])),
                         {'karma_embers': 9_999_999})
        self.assertEqual(adapter.maximums(document, {})['karma_embers'], 9_999_999)
        encoded = adapter.serialize(document, pending)
        self.assertEqual(adapter.decode(encoded, source=self.source).payload,
                         adapter.changed_payload(document, pending))
        edited = adapter.save_as(document, pending, self.folder / 'bound-edited.bin')
        self.assertEqual(parser.KARMA.value(edited.payload), 654)
        restored = adapter.restore(adapter.backup(document), self.folder / 'bound-restored.bin')
        self.assertTrue(restored.read_bytes() == document.raw)
        with self.assertRaises(SaveError):
            adapter.decode(document.raw, 'other_game', self.source)

    @unittest.skipUnless(native_source(), 'No private genuine Abyss copy with original owner sidecar.')
    def test_genuine_owner_roundtrip_targeted_edit_and_storage(self):
        original = parser.read_save(native_source())
        self.assertEqual(parser.serialize(original, {}), original.raw)
        with CNG_AES('CBC') as provider:
            reconstructed = parser.OUTER_MAGIC + provider.transform(
                parser.INNER_MAGIC + original.payload, parser._key(original.owner),
                direction='encrypt', iv=parser.IV)
        self.assertTrue(reconstructed == original.raw)
        parser.prepare_copy_context(original, self.folder / 'native-copy')
        source = self.folder / 'native-copy' / 'GAMEDATA00.BIN'
        source.write_bytes(original.raw)
        document = parser.read_save(source)
        current = parser.KARMA.value(document.payload)
        desired = current - 1 if 0 < current <= 9_999_999 else 1
        edited = parser.save_as(document, {'karma_embers': desired}, source.with_name('edited.bin'))
        self.assert_surgical(document, edited)
        self.assertEqual(parser.KARMA.value(edited.payload), desired)
        self.assertEqual(source.read_bytes(), original.raw)
        restored = parser.restore(parser.backup(document), source.with_name('restored.bin'))
        self.assertEqual(restored.read_bytes(), original.raw)

    def test_actual_tk_native_when_available(self):
        import tkinter as tk
        from koei_editor.games.abyss_pc.editor import Editor
        from koei_editor.games.abyss_pc.presentation import Presentation
        from koei_editor.shared.verified_gui import filedialog, messagebox
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.addCleanup(root.destroy)
        root.withdraw()
        source = self.source
        if native_source():
            document = parser.read_save(native_source())
            directory = self.folder / 'native-gui'
            parser.prepare_copy_context(document, directory)
            source = directory / 'GAMEDATA00.BIN'
            source.write_bytes(document.raw)
        editor = Editor(root)
        with patch.object(filedialog, 'askopenfilename', return_value=str(source)):
            editor.open()
        self.assertIsNotNone(editor.document)
        opened_raw = editor.document.raw
        self.assertTrue(editor.backup.exists())
        editor.search.set('Karma')
        root.update()
        self.assertEqual(editor.fields.get_children(), ('karma_embers',))
        editor.fields.selection_set('karma_embers')
        original = parser.KARMA.value(editor.document.payload)
        desired = original - 1 if 0 < original <= 9_999_999 else 1
        editor.value.set(str(desired))
        editor.apply_selected()
        self.assertEqual(editor.changes, {'karma_embers': desired})
        editor.review()
        editor.undo()
        self.assertEqual(editor.changes, {})
        editor.value.set(str(desired))
        editor.fields.selection_set('karma_embers')
        editor.apply_selected()
        destination = source.with_name('gui-edited.bin')
        with patch.object(filedialog, 'asksaveasfilename', return_value=str(destination)), \
                patch.object(messagebox, 'showinfo'), patch.object(messagebox, 'showerror') as errors:
            editor.save_as()
            errors.assert_not_called()
        reopened = parser.read_save(destination)
        self.assertEqual(parser.KARMA.value(reopened.payload), desired)
        self.assertTrue(source.read_bytes() == opened_raw)
        tables = Presentation(parser, parser.GAME_ID).inspection_tables(editor.document)
        self.assertEqual(len(tables[1].rows), 829)
        editor.apply_theme('Dark')
        root.update()


if __name__ == '__main__':
    unittest.main()
