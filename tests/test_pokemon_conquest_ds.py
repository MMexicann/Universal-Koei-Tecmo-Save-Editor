"""Native checksum/bit preservation, copy safety and actual Tk workflows."""
from dataclasses import replace
import os
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.pokemon_conquest_ds import parser
from koei_editor.shared.adapter_contract import BoundScalarAdapter
from tests.scalar_contract import ScalarContractTests


def fixture(size=0x40000, counts=(3, 2)):
    """Procedural structural/bit fixture, never a playable player save."""
    raw = bytearray(b'\xFF' * size)
    offset = 0
    for index, length in enumerate(parser.SECTION_SIZES * 2):
        raw[offset:offset + length] = bytes((i * 47 + index * 13) % 256 for i in range(length))
        dynamic = index % 13 in (7, 12)
        used = (parser.WARRIOR_BYTES + counts[index // 13] * 12
                if index % 13 == 12 else 1392 if dynamic else length - 24)
        struct.pack_into('<III', raw, offset, 0, used << 9 if dynamic else 0, 101 + index // 13)
        raw[offset + 12:offset + 24] = parser.TITLE_MARKER
        if index % 13 == 12:
            for slot in range(counts[index // 13]):
                base = offset + 24 + parser.WARRIOR_BYTES + slot * 12
                word1 = (0x80003039 | (1 << 15) | (8 << 20) | (17 << 25))
                word2 = 0xA5B0E0C3  # Speed=3; unrelated flags remain distinctive.
                struct.pack_into('<III', raw, base, (0, 56, 199)[slot % 3], word1, word2)
        struct.pack_into('<I', raw, offset, sum(raw[offset + 24:offset + 24 + used]))
        offset += length
    return bytes(raw)


INTEGRITY_OFFSETS = frozenset(position for base in parser.GALLERY_OFFSETS for position in range(base, base + 4))


class ConquestContractTests(ScalarContractTests, unittest.TestCase):
    game_id = parser.GAME_ID
    payload_integrity_offsets = INTEGRITY_OFFSETS

    def fixture_bytes(self):
        return fixture()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.game = SimpleNamespace(extension='.sav')
        self.adapter = BoundScalarAdapter(parser.GAME_ID, '.sav', parser)
        self.raw = fixture()
        self.source = self.folder / 'input-copy.sav'
        self.source.write_bytes(self.raw)
        self.document = self.adapter.read_save(self.source)


class ConquestFormatTests(unittest.TestCase):
    def test_complete_species_display_names_and_stable_native_ids(self):
        self.assertEqual(set(parser.SPECIES_NAMES), set(range(200)))
        self.assertEqual(len(set(parser.SPECIES_NAMES.values())), 200)
        for identity, name in ((0, 'Eevee'), (20, 'Jigglypuff'), (56, 'Forretress'),
                               (75, 'Dratini'), (97, 'Machop'), (110, 'Charizard'),
                               (155, 'Skorupi'), (195, 'Mewtwo'), (196, 'Reshiram'),
                               (197, 'Zekrom'), (198, 'Arceus'), (199, 'Rayquaza')):
            self.assertEqual(parser.SPECIES_NAMES[identity], name)
        doc = parser.decode(fixture())
        self.assertEqual([row[3] for row in parser.gallery_records(doc)[:3]],
                         ['Eevee', 'Forretress', 'Rayquaza'])

    def test_all_components_preserve_adjacent_bits_other_banks_and_counters(self):
        raw = fixture()
        doc = parser.decode(raw)
        self.assertEqual(parser.serialize(doc, {}), raw)
        self.assertEqual(len(parser.fields_for(doc)), 20)
        for field in parser.fields_for(doc):
            original = field.value(raw)
            for value in (0, 15, 31):
                staged = parser.stage(doc, {}, field.id, value)
                result = parser.serialize(doc, staged)
                old_word = struct.unpack_from('<I', raw, field.offset)[0]
                new_word = struct.unpack_from('<I', result, field.offset)[0]
                self.assertEqual(new_word, (old_word & ~(31 << field.shift)) | value << field.shift)
                self.assertEqual(field.value(result), value)
                checksum_base = parser.GALLERY_OFFSETS[0 if field.slot <= 1000 else 1]
                allowed = set(range(field.offset, field.offset + 4)) | set(range(checksum_base, checksum_base + 4))
                touched = {i for i, pair in enumerate(zip(raw, result)) if pair[0] != pair[1]}
                self.assertLessEqual(touched, allowed)
                self.assertEqual(parser.stage(doc, staged, field.id, original), {})
        self.assertEqual(doc.raw, raw)

    def test_packed_overlap_order_independence_and_bank_specific_bulk_max(self):
        doc = parser.decode(fixture())
        keys = [f'bank_1_pokemon_1_iv_{i}' for i in range(1, 5)]
        forward = dict(zip(keys, (4, 11, 24, 7)))
        backward = dict(reversed(tuple(forward.items())))
        self.assertEqual(parser.serialize(doc, forward), parser.serialize(doc, backward))
        self.assertEqual([parser.field_map(doc)[key].value(parser.serialize(doc, forward)) for key in keys],
                         [4, 11, 24, 7])
        changes = parser.maximums(doc, {}, 'Gallery bank 1 IVs')
        out = parser.serialize(doc, changes)
        self.assertEqual(out[parser.BANK_SIZE:], doc.raw[parser.BANK_SIZE:])
        self.assertTrue(all(field.value(out) == 31 for field in parser.fields_for(doc)
                            if field.group == 'Gallery bank 1 IVs' and field.maxable))
        all_max = parser.serialize(doc, parser.maximums(doc, {}))
        self.assertTrue(all(field.value(all_max) == 31 for field in parser.fields_for(doc) if field.maxable))
        forretress = parser.field_map(doc)['bank_1_pokemon_2_iv_4']
        self.assertFalse(forretress.maxable)
        self.assertEqual(forretress.value(all_max), forretress.value(doc.raw))
        self.assertEqual(parser.limit_values(doc, {}, [forretress.id]), {})
        self.assertEqual(forretress.value(parser.serialize(doc, {forretress.id: 0})), 0)
        # Assigning already maxed values creates no changes and no checksum normalization.
        self.assertEqual(parser.maximums(parser.decode(all_max), {}), {})

    def test_every_section_integrity_title_lengths_region_container_and_tail_rejected(self):
        raw = fixture()
        for invalid in (raw[:-1], raw + b'\0', bytes(len(raw)), bytearray(raw),
                        b'ARDS' + b'\0' * 496 + raw, raw + b'|-DESMUME SAVE-|'):
            with self.assertRaises(SaveError):
                parser.decode(invalid)
        for _index, offset, _size, _length, _checksum, _generation in parser._sections(raw):
            for position in (offset, offset + 12, offset + 24):
                changed = bytearray(raw)
                changed[position] ^= 1
                with self.assertRaises(SaveError):
                    parser.decode(bytes(changed))
        for value in (0, 1, (0x40000 << 9), (parser.WARRIOR_BYTES + 1) << 9):
            changed = bytearray(raw)
            struct.pack_into('<I', changed, parser.GALLERY_OFFSETS[0] + 4, value)
            with self.assertRaises(SaveError):
                parser.decode(bytes(changed))
        changed = bytearray(raw)
        changed[-1] = 0
        with self.assertRaises(SaveError):
            parser.decode(bytes(changed))
        self.assertEqual(parser.serialize(parser.decode(fixture(0x80000)), {}), fixture(0x80000))

    def test_unknown_records_readonly_forged_snapshot_and_unmapped_mechanics_rejected(self):
        raw = bytearray(fixture())
        base = parser.GALLERY_OFFSETS[0]
        struct.pack_into('<I', raw, base + 24 + parser.WARRIOR_BYTES, 0xF0000038)
        length = struct.unpack_from('<I', raw, base + 4)[0] >> 9
        struct.pack_into('<I', raw, base, sum(raw[base + 24:base + 24 + length]))
        doc = parser.decode(bytes(raw))
        self.assertEqual(len(parser.fields_for(doc)), 16)
        self.assertEqual(parser.gallery_records(doc)[0][-1], 'Preserved unknown record')
        for key in ('bank_1_pokemon_1_iv_1', 'gold', 'scenario_exp', 'species', 'warrior_link', 'complete_story'):
            with self.assertRaises(SaveError):
                parser.stage(doc, {}, key, 1)
        key = parser.fields_for(doc)[0].id
        for value in (-1, 32, True, '15', 1.0):
            with self.assertRaises(SaveError):
                parser.stage(doc, {}, key, value)
        for forged in (replace(doc, payload=doc.payload[:-1]), replace(doc, raw=bytearray(doc.raw)),
                       replace(doc, format=replace(parser.FORMAT, id='different_game'))):
            with self.assertRaises(SaveError):
                parser.serialize(forged, {})
        with self.assertRaises(SaveError):
            parser.decode(bytes(raw), 'hyrule_legends')

    def test_stale_source_backup_and_source_change_during_save_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'copy.sav'
            destination = Path(temporary) / 'result.sav'
            source.write_bytes(fixture())
            doc = parser.read_save(source)
            changed = doc.raw[:-1] + b'\0'
            source.write_bytes(changed)
            with self.assertRaises(SaveError):
                parser.backup(doc)
            source.write_bytes(doc.raw)
            actual_backup = parser.snapshot_backup
            def changing_backup(raw, path, game, folder):
                result = actual_backup(raw, path, game, folder)
                source.write_bytes(changed)
                return result
            with patch.object(parser, 'snapshot_backup', side_effect=changing_backup):
                with self.assertRaises(SaveError):
                    parser.save_as(doc, {'bank_1_pokemon_1_iv_4': 31}, destination)
            self.assertFalse(destination.exists())
            self.assertEqual(source.read_bytes(), changed)

    def test_genuine_copies_varied_record_counts_all_integrity_and_writer_masks(self):
        folder = os.environ.get('POKEMON_CONQUEST_NATIVE_DIR')
        if not folder:
            self.skipTest('Private genuine Pokémon Conquest raw copies are unavailable.')
        paths = sorted(Path(folder).glob('conquest-*.sav'))
        self.assertGreaterEqual(len(paths), 3)
        distinct = set()
        counts = set()
        for path in paths:
            doc = parser.read_save(path)
            distinct.add(doc.sha256)
            self.assertEqual(parser.serialize(doc, {}), doc.raw)
            counts.add(len(parser.gallery_records(doc)))
            # Compare every occupied mapped component against an independently
            # applied bit mask; test both native generations and dynamic counts.
            fields = parser.fields_for(doc)
            for field in fields:
                value = 31 if field.value(doc.raw) != 31 else 0
                result = parser.serialize(doc, {field.id: value})
                word = struct.unpack_from('<I', doc.raw, field.offset)[0]
                expected = (word & ~(31 << field.shift)) | value << field.shift
                self.assertEqual(struct.unpack_from('<I', result, field.offset)[0], expected)
                checksum_base = parser.GALLERY_OFFSETS[0 if field.slot <= 1000 else 1]
                before = bytearray(doc.raw)
                struct.pack_into('<I', before, field.offset, expected)
                used = struct.unpack_from('<I', before, checksum_base + 4)[0] >> 9
                struct.pack_into('<I', before, checksum_base,
                                 sum(before[checksum_base + 24:checksum_base + 24 + used]))
                self.assertEqual(result, bytes(before))
        self.assertEqual(len(distinct), len(paths))
        self.assertGreaterEqual(len(counts), 3)
        from koei_editor.shared.verified_self_test import _run
        with tempfile.TemporaryDirectory() as temporary:
            report = _run(BoundScalarAdapter(parser.GAME_ID, '.sav', parser),
                          parser.GAME_ID, paths[0], Path(temporary) / 'copied-test')
            self.assertTrue(report['success'])
            self.assertTrue(report['native_integrity_verified'])
            self.assertFalse(report['in_game_load_tested'])

    def test_real_tk_open_stage_undo_review_save_and_searchable_gallery(self):
        import tkinter as tk
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest('Tk display is unavailable.')
        self.addCleanup(root.destroy)
        from koei_editor.games.pokemon_conquest_ds.editor import Editor
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'copy.sav'
            destination = Path(temporary) / 'edited.sav'
            native_folder = os.environ.get('POKEMON_CONQUEST_NATIVE_DIR')
            paths = sorted(Path(native_folder).glob('conquest-*.sav')) if native_folder else []
            raw = paths[0].read_bytes() if paths else fixture()
            source.write_bytes(raw)
            editor = Editor(root)
            root.update()
            with patch('koei_editor.shared.verified_gui.filedialog.askopenfilename', return_value=str(source)):
                editor.open()
            root.update()
            key = 'bank_1_pokemon_1_iv_4'
            # Use the same staged/Undo pathway as scalar GUI controls.
            editor.stage_values({key: 31})
            self.assertEqual(editor.changes, {key: 31})
            editor.undo()
            self.assertEqual(editor.changes, {})
            editor.changes = parser.stage(editor.document, {}, key, 31)
            self.assertEqual(len(parser.review(editor.document, editor.changes)), 1)
            editor.review()
            root.update()
            reviews = [window for window in root.winfo_children()
                       if isinstance(window, tk.Toplevel) and window.title() == 'Review Changes']
            self.assertEqual(len(reviews), 1)
            reviews[0].destroy()
            with patch('koei_editor.shared.verified_gui.filedialog.asksaveasfilename', return_value=str(destination)), \
                    patch('koei_editor.shared.verified_gui.messagebox.showinfo'):
                editor.save_as()
            self.assertEqual(parser.read_save(destination).payload, parser.serialize(parser.decode(source.read_bytes()), {key: 31}))
            tables = editor.presentation.inspection_tables(editor.document)
            self.assertTrue(any('Eevee' in str(row) for row in tables[0].rows))
            self.assertEqual(source.read_bytes(), raw)


if __name__ == '__main__':
    unittest.main()
