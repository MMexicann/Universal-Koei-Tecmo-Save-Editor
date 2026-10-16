"""Procedural EU Troy PROFILE regressions and optional native-copy validation."""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.troy_ps3 import parser
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from koei_editor.shared import ps3_copy
from tests import test_ps3_expansion as ps3_context
from tests.scalar_contract import ScalarContractTests


def checksum(raw):
    result = bytearray(raw)
    struct.pack_into('>I', result, len(result) - 4, zlib.crc32(result[:-4]))
    return bytes(result)


def fixture():
    """Structural test data with invented native-string identities; no player data."""
    raw = bytearray((i * 37 + 11) & 255 for i in range(parser.SAVE_SIZE))
    raw[:len(parser.HEADER)] = parser.HEADER
    position = parser.MUSIC_BASE
    struct.pack_into('>I', raw, position, 53)
    position += 4
    for index in range(53):
        text = f'Bgm{index:03d}\0'.encode('utf-16-be')
        struct.pack_into('>I', raw, position, len(text) // 2)
        position += 4
        raw[position:position + len(text)] = text
        position += len(text)
    struct.pack_into('>I', raw, position, 42)
    position += 4
    raw[position:position + 42] = bytes(index % 2 for index in range(42))
    position += 42
    raw[position:parser.ITEM_BASE] = bytes((index * 13) & 255
                                          for index in range(parser.ITEM_BASE - position))
    struct.pack_into('>I', raw, parser.KLEOS_OFFSET, 4498)
    struct.pack_into('>I', raw, parser.ITEM_BASE, 99)
    position = parser.ITEM_BASE + 4
    # The qualified size leaves 8,100 bytes for the 99 length-prefixed names.
    # First name has the source writer's length anchor (41 UTF-16 code units).
    lengths = [41] + [38] * 98
    lengths[1] += (8100 - sum(4 + 2 * size for size in lengths)) // 2
    for index, length in enumerate(lengths):
        text = f'Items.SkillItem.Procedural_{index:03d}'
        text += 'X' * (length - 1 - len(text))
        encoded = (text + '\0').encode('utf-16-be')
        struct.pack_into('>I', raw, position, length)
        position += 4
        raw[position:position + len(encoded)] = encoded
        position += len(encoded)
    struct.pack_into('>I', raw, position, 99)
    position += 4
    for index in range(99):
        struct.pack_into('>I', raw, position, 2500 + index)
        raw[position + 4:position + 6] = bytes((index % 2, (index + 1) % 2))
        position += 6
    raw[position:position + 5] = b'\x01\0\0\0\x0f'
    assert position + 9 == len(raw)
    return checksum(raw)


def copied_save(folder, raw=None, metadata=None):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'PROFILE'
    path.write_bytes(fixture() if raw is None else raw)
    (folder / 'PARAM.SFO').write_bytes(metadata if metadata is not None else
        ps3_context.PS3ContextTests.metadata(parser.TITLE_DIRECTORY))
    return path


class TroyPS3Tests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.path = copied_save(self.folder / 'source')
        self.adapter = BoundScalarAdapter(parser.GAME_ID, '', parser)
        self.document = self.adapter.read_save(self.path)

    def destination(self, name='output'):
        path = copied_save(self.folder / name, metadata=(self.path.parent / 'PARAM.SFO').read_bytes())
        path.unlink()
        return path

    def test_registered_profile_and_copied_save_cli_contract(self):
        from koei_editor.game_registry import get_game
        from koei_editor.shared.verified_self_test import run
        game = get_game(parser.GAME_ID)
        self.assertEqual(game.platform, 'PlayStation 3')
        self.assertEqual(game.extension, '')
        self.assertIs(game.get_scalar_adapter().backend, parser)
        report = run(parser.GAME_ID, self.path, self.folder / 'self-test')
        self.assertTrue(report['success'])
        self.assertTrue(report['native_integrity_verified'])
        self.assertEqual(report['fields_checked'], 1)
        self.assertEqual(report['fields_changed'], 0)
        self.assertFalse(report['in_game_load_tested'])
        self.assertEqual((self.folder / 'self-test/PARAM.SFO').read_bytes(),
                         (self.path.parent / 'PARAM.SFO').read_bytes())

    def test_native_scalar_recipe_decimal_offset_roundtrip_and_surgery(self):
        self.assertEqual(parser.serialize(self.document, {}), self.document.raw)
        field = self.adapter.field_map(self.document)['kleos']
        self.assertEqual(field.offset, 0x17200)
        for value in (0, 1, 1234, 4497, 4498):
            with self.subTest(value=value):
                changes = self.adapter.stage(self.document, {}, 'kleos', value)
                raw = self.adapter.serialize(self.document, changes)
                reopened = self.adapter.decode(raw)
                self.assertEqual(field.value(reopened.payload), value)
                self.assertEqual(zlib.crc32(raw[:-4]), int.from_bytes(raw[-4:], 'big'))
                allowed = set(range(field.offset, field.offset + 4)) | set(parser.CHECKSUM_OFFSETS)
                touched = {i for i, pair in enumerate(zip(raw, self.document.raw)) if pair[0] != pair[1]}
                self.assertLessEqual(touched, allowed)
                self.assertEqual(raw[:field.offset], self.document.raw[:field.offset])
                self.assertEqual(raw[field.offset + 4:-4], self.document.raw[field.offset + 4:-4])
        self.assertEqual(self.path.read_bytes(), self.document.raw)

    def test_reduce_only_hard_constraints_even_experimental_and_no_max(self):
        for adapter in (self.adapter, BoundScalarAdapter(parser.GAME_ID, '', parser, experimental=True)):
            for value in (-1, 4499, 4294967295, True, '1', 1.0):
                with self.subTest(experimental=adapter.experimental, value=value), self.assertRaises(SaveError):
                    adapter.stage(self.document, {}, 'kleos', value)
        pending = self.adapter.stage(self.document, {}, 'kleos', 123)
        self.assertEqual(pending, {'kleos': 123})
        self.assertEqual(self.adapter.stage(self.document, pending, 'kleos', 4498), {})
        self.assertEqual(self.adapter.maximums(self.document, pending), pending)
        self.assertEqual(self.adapter.limit_values(self.document, pending, ['kleos']), {})
        self.assertEqual(self.adapter.review(self.document, pending)[0][1:], (4498, 123))
        self.assertEqual(pending, {'kleos': 123})

    def test_complete_pending_map_and_forged_snapshots_rejected(self):
        for changes in (None, [], {'kleos': True}, {'unknown': 1}, {0: 1}, {'kleos': -1}):
            for action in (self.adapter.serialize, self.adapter.review, self.adapter.maximums):
                with self.subTest(changes=changes, action=action.__name__), self.assertRaises(SaveError):
                    action(self.document, changes)
        for document in (replace(self.document, format=parser.Format()),
                         replace(self.document, payload=bytearray(self.document.raw)),
                         replace(self.document, raw=bytearray(self.document.raw)),
                         replace(self.document, source=None), replace(self.document, context_digest=None)):
            with self.assertRaises(SaveError):
                self.adapter.serialize(document, {})

    def test_all_covered_bytes_crc_and_foreign_formats_rejected(self):
        for offset in (0, 7, 0x100, 0x16E06, 0x17200, 0x19402, parser.SAVE_SIZE - 1):
            changed = bytearray(self.document.raw)
            changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(SaveError):
                self.adapter.decode(bytes(changed))
        for raw in (self.document.raw[:-1], self.document.raw + b'\0', bytearray(self.document.raw),
                    b'\0' * parser.SAVE_SIZE, b'CON ' + self.document.raw[4:]):
            with self.assertRaises(SaveError):
                self.adapter.decode(raw)

    def test_resealed_malformed_table_counts_lengths_identity_and_boundaries_rejected(self):
        for offset, value in ((0, 39), (parser.MUSIC_BASE, 52),
                              (parser.MUSIC_BASE + 4, 129), (parser.ITEM_BASE, 98),
                              (parser.ITEM_BASE + 4, 0), (0x191AC, 98)):
            raw = bytearray(self.document.raw)
            struct.pack_into('>I', raw, offset, value)
            with self.subTest(offset=offset, value=value), self.assertRaises(SaveError):
                self.adapter.decode(checksum(raw))
        for offset in (parser.MUSIC_BASE + 4 + 4, parser.ITEM_BASE + 4 + 4):
            raw = bytearray(self.document.raw)
            raw[offset:offset + 2] = b'\0Z'
            with self.assertRaises(SaveError):
                self.adapter.decode(checksum(raw))

    def test_unknown_item_words_flags_and_higher_wallet_stay_opaque(self):
        raw = bytearray(self.document.raw)
        raw[0x191B0:0x191B6] = b'\xff' * 6
        struct.pack_into('>I', raw, parser.KLEOS_OFFSET, 0xFFFFFFFF)
        document = self.adapter.decode(checksum(raw))
        self.assertEqual(self.adapter.field_map(document), {})
        self.assertEqual(self.adapter.maximums(document, {}), {})
        for amount in (0, 0x7FFFFFFF, 0xFFFFFFFE, 0xFFFFFFFF):
            with self.assertRaises(SaveError):
                self.adapter.stage(document, {}, 'kleos', amount)
        output = self.adapter.serialize(document, {})
        self.assertEqual(output, document.raw)
        self.assertEqual(output[0x191B0:0x191B6], b'\xff' * 6)
        self.assertEqual(len(parser.inspection_rows(document)), 153)
        self.assertIn('read only', parser.inspection_rows(document)[0]['value'])

    def test_positive_word_boundary_is_reduce_only_without_claiming_a_cap(self):
        for opened in (0, 0x7FFFFFFF, 0x80000000):
            raw = bytearray(self.document.raw)
            struct.pack_into('>I', raw, parser.KLEOS_OFFSET, opened)
            document = self.adapter.decode(checksum(raw))
            self.assertEqual(self.adapter.serialize(document, {}), document.raw)
            if opened <= parser.MAX_QUALIFIED_KLEOS:
                self.assertEqual(self.adapter.stage(document, {}, 'kleos', opened), {})
                encoded = self.adapter.serialize(document, {'kleos': 0})
                self.assertEqual(int.from_bytes(encoded[parser.KLEOS_OFFSET:parser.KLEOS_OFFSET + 4], 'big'), 0)
            else:
                self.assertEqual(self.adapter.fields_for(document), ())

    def test_source_context_and_destination_identity_safety_backup_and_restore(self):
        destination = self.destination()
        metadata = (self.path.parent / 'PARAM.SFO').read_bytes()
        opened = self.adapter.save_as(self.document, {'kleos': 1234}, destination)
        self.assertEqual(opened.raw[0x17200:0x17204], (1234).to_bytes(4, 'big'))
        self.assertEqual(self.path.read_bytes(), self.document.raw)
        self.assertEqual((destination.parent / 'PARAM.SFO').read_bytes(), metadata)
        backups = list((self.path.parent / 'UniversalEditorBackups').glob('PROFILE-*'))
        backups = [path for path in backups if not path.suffix]
        self.assertEqual(len(backups), 1)
        restored = self.adapter.restore(backups[0], destination.parent / 'restored')
        self.assertEqual(restored.read_bytes(), self.document.raw)
        with self.assertRaises(FileExistsError):
            self.adapter.save_as(self.document, {}, destination)
        with self.assertRaises(FileExistsError):
            self.adapter.save_as(self.document, {}, self.path)
        with self.assertRaises(SaveError):
            self.adapter.save_as(self.document, {}, destination.with_suffix('.bin'))
        (destination.parent / 'PARAM.SFO').write_bytes(metadata + b'opaque context changed')
        with self.assertRaises(SaveError):
            self.adapter.restore(backups[0], destination.parent / 'foreign')
        with self.assertRaises(SaveError):
            self.adapter.save_as(self.document, {}, destination.parent / 'foreign')

    def test_original_metadata_required_and_wrong_regions_or_damaged_source_rejected(self):
        for identity in ('BLUS30502-WLOT', 'BLES01183-OTHER', 'BLUS30873-SAVEDATA'):
            path = copied_save(self.folder / identity, metadata=ps3_context.PS3ContextTests.metadata(identity))
            with self.assertRaises(SaveError):
                self.adapter.read_save(path)
        metadata = self.path.parent / 'PARAM.SFO'
        metadata.unlink()
        with self.assertRaises(SaveError):
            self.adapter.read_save(self.path)
        metadata.write_bytes(ps3_context.PS3ContextTests.metadata(parser.TITLE_DIRECTORY))
        destination = self.destination()
        self.path.write_bytes(self.document.raw + b'changed')
        with self.assertRaises(SaveError):
            self.adapter.save_as(self.document, {}, destination)
        self.assertFalse(destination.exists())

    def test_late_context_race_retains_output_but_reports_failure(self):
        destination = self.destination()
        original = ps3_copy.atomic_new
        mutations = []
        def mutate(raw, path):
            result = original(raw, path)
            if destination.exists() and Path(path).samefile(destination):
                metadata = destination.parent / 'PARAM.SFO'
                metadata.write_bytes(metadata.read_bytes() + b'changed')
                mutations.append(1)
            return result
        with patch.object(ps3_copy, 'atomic_new', side_effect=mutate), self.assertRaises(SaveError):
            self.adapter.save_as(self.document, {'kleos': 1}, destination)
        self.assertEqual(mutations, [1])
        self.assertTrue(destination.exists())
        self.assertEqual(self.path.read_bytes(), self.document.raw)

    def test_complete_metadata_change_while_opening_is_rejected(self):
        actual = parser.context_raw
        calls = []
        metadata = self.path.parent / 'PARAM.SFO'
        def mutate_after_first_snapshot(path):
            snapshot = actual(path)
            calls.append(1)
            if len(calls) == 1:
                metadata.write_bytes(snapshot + b'opaque metadata changed')
            return snapshot
        with patch.object(parser, 'context_raw', side_effect=mutate_after_first_snapshot):
            with self.assertRaisesRegex(SaveError, 'metadata changed while opening'):
                self.adapter.read_save(self.path)
        self.assertEqual(calls, [1, 1])
        self.assertEqual(self.path.read_bytes(), self.document.raw)

    def test_post_creation_source_change_rejects_success_and_preserves_backup(self):
        destination = self.destination()
        actual = ps3_copy.atomic_new
        mutations = []
        def mutate_after_output(raw, path):
            result = actual(raw, path)
            if destination.exists() and Path(path).samefile(destination):
                self.path.write_bytes(self.document.raw[:-1])
                mutations.append(1)
            return result
        with patch.object(ps3_copy, 'atomic_new', side_effect=mutate_after_output):
            with self.assertRaisesRegex(SaveError, 'opened PS3 copy changed'):
                self.adapter.save_as(self.document, {'kleos': 123}, destination)
        self.assertEqual(mutations, [1])
        self.assertTrue(destination.exists())
        snapshots = [path for path in (self.path.parent / 'UniversalEditorBackups').glob('PROFILE-*')
                     if not path.suffix]
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].read_bytes(), self.document.raw)

    def test_crc_valid_destination_replacement_rejected_without_deletion(self):
        destination = self.destination()
        actual = ps3_copy.atomic_new
        mutations = []
        def replace_after_output(raw, path):
            result = actual(raw, path)
            if destination.exists() and Path(path).samefile(destination):
                destination.write_bytes(self.document.raw)
                mutations.append(1)
            return result
        with patch.object(ps3_copy, 'atomic_new', side_effect=replace_after_output):
            with self.assertRaisesRegex(SaveError, 'changed during read-back'):
                self.adapter.save_as(self.document, {'kleos': 123}, destination)
        self.assertEqual(mutations, [1])
        self.assertEqual(destination.read_bytes(), self.document.raw)

    def test_searchable_native_names_and_read_only_status_inspection(self):
        from koei_editor.games.troy_ps3.editor import Presentation
        rows = parser.inspection_rows(self.document)
        self.assertEqual(len(rows), 1 + 53 + 99)
        self.assertEqual(rows[0]['group'], 'Resources')
        self.assertEqual(rows[1]['group'], 'Music collection')
        self.assertIn('Procedural_000', rows[54]['label'])
        presentation = Presentation(parser, parser.GAME_ID)
        self.assertEqual(len(presentation.inspection_tables(self.document)[0].rows), 153)
        self.assertTrue(parser.field_hint(self.document, 'kleos'))

    def test_actual_tk_edit_search_review_undo_and_safe_save(self):
        import tkinter as tk
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.addCleanup(root.destroy)
        root.withdraw()
        from koei_editor.games.troy_ps3.editor import Editor
        errors = []
        with patch('koei_editor.shared.verified_gui.messagebox.showerror',
                   side_effect=lambda *args: errors.append(args)), \
                patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(self.path)):
            editor = Editor(root)
            editor.open()
            editor.search.set('Kleos')
            editor.refresh()
            self.assertEqual(editor.fields.get_children(), ('kleos',))
            editor.fields.selection_set('kleos')
            editor.value.set('42')
            editor.apply_selected()
            self.assertEqual(editor.changes, {'kleos': 42})
            editor.review()
            editor.undo()
            self.assertEqual(editor.changes, {})
            editor.max_visible()
            self.assertEqual(editor.changes, {})
            editor.stage_values({'kleos': 42})
            editor.show_inspector()
            destination = self.destination('gui')
            editor.save_to(destination)
            self.assertEqual(parser.field_map(editor.document)['kleos'].value(editor.document.payload), 42)
            self.assertFalse(errors)
            self.assertEqual(self.path.read_bytes(), self.document.raw)

    def test_native_copied_profile_roundtrip_surgery_backup_restore_when_supplied(self):
        value = os.environ.get('TROY_PS3_NATIVE_DIR')
        if not value:
            self.skipTest('Set TROY_PS3_NATIVE_DIR to a qualified decrypted PROFILE + original PARAM.SFO.')
        original = Path(value) / 'PROFILE'
        raw, metadata = original.read_bytes(), (original.parent / 'PARAM.SFO').read_bytes()
        before = hashlib.sha256(raw).hexdigest()
        source = copied_save(self.folder / 'native', raw, metadata)
        document = self.adapter.read_save(source)
        self.assertEqual(self.adapter.serialize(document, {}), raw)
        self.assertGreater(parser.field_map(document)['kleos'].value(raw), 0)
        for amount in (0, 1, 1234, 4497):
            changes = self.adapter.stage(document, {}, 'kleos', amount)
            output = self.adapter.serialize(document, changes)
            allowed = set(range(parser.KLEOS_OFFSET, parser.KLEOS_OFFSET + 4)) | set(parser.CHECKSUM_OFFSETS)
            self.assertLessEqual({i for i, pair in enumerate(zip(output, raw)) if pair[0] != pair[1]}, allowed)
        opened = self.adapter.save_as(document, {'kleos': 1234}, source.parent / 'edited')
        self.assertEqual(parser.field_map(opened)['kleos'].value(opened.raw), 1234)
        backup = self.adapter.backup(document)
        self.assertEqual(self.adapter.restore(backup, source.parent / 'restored').read_bytes(), raw)
        self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(), before)
        self.assertEqual((original.parent / 'PARAM.SFO').read_bytes(), metadata)


class TroyPS3ScalarContract(ScalarContractTests, unittest.TestCase):
    game_id = parser.GAME_ID
    payload_integrity_offsets = frozenset(parser.CHECKSUM_OFFSETS)

    def fixture_bytes(self):
        return fixture()

    def setUp(self):
        # The generic contract deliberately knows no account/console metadata.
        # Supply this adapter's required opaque original context locally.
        from koei_editor.game_registry import get_game
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.game = get_game(self.game_id)
        self.adapter = self.game.get_scalar_adapter()
        self.raw = self.fixture_bytes()
        self.source = copied_save(self.folder, self.raw)
        self.document = self.adapter.read_save(self.source)


if __name__ == '__main__':
    unittest.main()
