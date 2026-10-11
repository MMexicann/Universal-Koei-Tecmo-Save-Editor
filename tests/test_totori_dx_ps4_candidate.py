"""Procedural framing/title tests and optional genuine decrypted PS4 inspection."""
from dataclasses import replace
import os
from pathlib import Path
import re
import struct
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.research.totori_dx_ps4 import inspection as candidate
from tests.test_rorona_dx_candidate import procedural_candidate as rorona_candidate


def procedural_sfo(title='CUSA14014', directory='GAMEDATA00', extras=()):
    """Minimal identity-only test SFO; no player account or signing values."""
    pairs = [('TITLE_ID', title), ('SAVEDATA_DIRECTORY', directory), *extras]
    keys = b''
    values = b''
    records = []
    for key, value in pairs:
        encoded = value.encode('ascii') + b'\0'
        records.append((len(keys), 0x204, len(encoded), len(encoded), len(values)))
        keys += key.encode('ascii') + b'\0'
        values += encoded
    key_offset = 20 + len(records) * 16
    data_offset = key_offset + len(keys)
    return (struct.pack('<5I', 0x46535000, 0x101, key_offset, data_offset, len(records))
            + b''.join(struct.pack('<HHIII', *record) for record in records)
            + keys + values)


def procedural_candidate():
    """Distinctive opaque bytes, not a manufactured playable game save."""
    raw = bytearray((index * 37 + 13) % 256 for index in range(candidate.SAVE_SIZE))
    struct.pack_into('<I', raw, 0, candidate.MAGIC)
    offset = candidate.HEADER_SIZE
    positions = {}
    for tag, size in enumerate(candidate.CHUNK_SIZES, 1):
        struct.pack_into('<II', raw, offset, tag, size)
        positions[tag] = offset + 8
        offset += 8 + size
    struct.pack_into('<II', raw, offset, candidate.TRAILER_TAG, candidate.TRAILER_SIZE)
    struct.pack_into('<I', raw, positions[3], 123456)
    struct.pack_into('<I', raw, positions[15] + 4, 23456)
    struct.pack_into('<I', raw, positions[18], 34567)
    struct.pack_into('<3I', raw, positions[11] + 8, 3, 5, 7)
    for index in range(candidate.CHARACTER_COUNT):
        struct.pack_into('<3i', raw, positions[4] + index * candidate.CHARACTER_SIZE,
                         index, 20 + index, 1000 + index)
    for index in range(candidate.BASKET_COUNT + candidate.CONTAINER_COUNT):
        struct.pack_into('<iif10i', raw, positions[7] + index * candidate.ITEM_SIZE,
                         -1, -1, 50.0, *([-1] * 10))
    struct.pack_into('<iif10i', raw, positions[7], 10, 20, 60.0,
                     1, 2, -1, -1, -1, 3, -1, -1, -1, 0)
    struct.pack_into('<4i', raw, positions[7] + 1099 * candidate.ITEM_SIZE,
                     60, 999, 11, 12)
    return bytes(raw)


class TotoriPS4CandidateTests(unittest.TestCase):
    def test_exact_title_framing_leads_and_no_writer_claim(self):
        raw = procedural_candidate()
        document = candidate.inspect(raw, procedural_sfo())
        self.assertEqual(candidate.unchanged(document), raw)
        self.assertEqual(document.cole, 123456)
        self.assertEqual(document.alchemy_exp_lead, 23456)
        self.assertEqual(document.adventurer_points_lead, 34567)
        self.assertEqual(document.zero_based_calendar_lead, (3, 5, 7))
        self.assertEqual(len(document.characters[0].stored_stat_bonuses), 6)
        self.assertEqual(document.chunks[2].payload_offset, 0xB3FC)
        self.assertEqual(document.chunks[3].payload_offset, 0xB408)
        self.assertEqual(document.chunks[6].payload_offset, 0x3179F)
        self.assertEqual(document.trailer_offset, 0x46E39)
        self.assertEqual(len(document.characters), 10)
        self.assertEqual(len(document.items), 1099)
        self.assertEqual((document.basket_limit, document.container_limit), (60, 999))
        self.assertTrue(document.items[0].ordinary_shape)
        self.assertTrue(document.items[-1].canonical_empty)
        self.assertEqual((document.items[99].collection, document.items[99].index), ('Basket', 99))
        self.assertEqual((document.items[100].collection, document.items[100].index), ('Container', 0))
        self.assertFalse(document.editable)
        self.assertFalse(document.qualified_game_profile)
        self.assertFalse(document.integrity_qualified)
        self.assertFalse(hasattr(candidate, 'serialize'))
        self.assertFalse(hasattr(candidate, 'save_as'))
        self.assertNotEqual(raw[4:32], bytes(28))
        self.assertNotEqual(raw[document.trailer_offset + 8:], bytes(document.trailer_size - 8))

    def test_same_sized_rorona_system_alternate_mutable_and_foreign_inputs(self):
        raw = procedural_candidate()
        for bad in (raw[:-1], raw + b'\0', raw[:36864], raw[:336112], rorona_candidate(),
                    bytearray(raw), memoryview(raw), bytes(len(raw))):
            with self.subTest(kind=type(bad), size=len(bad)), self.assertRaises(SaveError):
                candidate.inspect(bad, procedural_sfo())
        for title, directory in (('CUSA14013', 'GAMEDATA00'), ('CUSA14014', 'SYSTEMDATA'),
                                 ('CUSA14014', 'GAMEDATA01'), ('', 'GAMEDATA00')):
            with self.subTest(title=title, directory=directory), self.assertRaises(SaveError):
                candidate.inspect(raw, procedural_sfo(title, directory))

    def test_every_chunk_tag_and_length_and_trailer_are_bounded(self):
        raw = procedural_candidate()
        document = candidate.inspect(raw, procedural_sfo())
        for chunk in document.chunks:
            for relative, value in ((0, chunk.tag + 1), (4, chunk.size + 1), (4, 0xFFFFFFFF)):
                bad = bytearray(raw)
                struct.pack_into('<I', bad, chunk.header_offset + relative, value)
                with self.subTest(tag=chunk.tag, relative=relative), self.assertRaises(SaveError):
                    candidate.inspect(bytes(bad), procedural_sfo())
        for relative, value in ((0, 0), (4, document.trailer_size - 8), (4, 0xFFFFFFFF)):
            bad = bytearray(raw)
            struct.pack_into('<I', bad, document.trailer_offset + relative, value)
            with self.assertRaises(SaveError):
                candidate.inspect(bytes(bad), procedural_sfo())

    def test_metadata_duplicates_missing_values_bounds_and_encoding_rejected(self):
        raw = procedural_candidate()
        sfo = procedural_sfo()
        malformed = [b'', sfo[:19], bytes(4097), bytearray(sfo),
                     procedural_sfo(extras=(('TITLE_ID', 'CUSA14014'),))]
        for offset, fmt, value in ((0, '<I', 0), (4, '<I', 0x102), (8, '<I', 0),
                                   (16, '<I', 129), (20, '<H', 0xFFFF),
                                   (22, '<H', 0x404), (24, '<I', 129),
                                   (28, '<I', 129), (32, '<I', 0xFFFFFFFF)):
            bad = bytearray(sfo)
            struct.pack_into(fmt, bad, offset, value)
            malformed.append(bytes(bad))
        malformed.append(sfo.replace(b'TITLE_ID\0', b'TITLX_ID\0'))
        malformed.append(sfo[:-1] + b'X')
        malformed.append(sfo.replace(b'CUSA14014\0', b'CUSA\x801014\0'))
        for bad in malformed:
            with self.subTest(kind=type(bad)), self.assertRaises(SaveError):
                candidate.inspect(raw, bad)

    def test_opaque_metadata_not_retained_and_unusual_record_bytes_preserved(self):
        raw = procedural_candidate()
        first = candidate.inspect(raw, procedural_sfo(extras=(('UNRELATED', 'opaque'),)))
        second = candidate.inspect(raw, procedural_sfo(extras=(('UNRELATED', 'different'),)))
        self.assertEqual(first, second)
        bad = bytearray(raw)
        # Above-natural, NaN and unfamiliar IDs are preserved research values.
        struct.pack_into('<I', bad, first.items[0].offset + 8, 0x7FC00001)
        struct.pack_into('<i', bad, first.items[0].offset + 4, 999999)
        document = candidate.inspect(bytes(bad), procedural_sfo())
        self.assertFalse(document.items[0].ordinary_shape)
        self.assertEqual(candidate.unchanged(document), bytes(bad))

    def test_forged_inspections_cannot_claim_integrity_or_roundtrip(self):
        document = candidate.inspect(procedural_candidate(), procedural_sfo())
        for bad in (None, replace(document, raw=bytearray(document.raw)),
                    replace(document, integrity_qualified=True), replace(document, editable=True),
                    replace(document, qualified_game_profile=True), replace(document, title_id='CUSA14013'),
                    replace(document, cole=document.cole + 1), replace(document, items=document.items[:-1]),
                    replace(document, characters=document.characters[:-1]), replace(document, basket_limit=100)):
            with self.subTest(kind=type(bad)), self.assertRaises(SaveError):
                candidate.unchanged(bad)

    def test_optional_genuine_copied_decrypted_ps4_exports(self):
        selected = os.environ.get('TOTORI_DX_PS4_CANDIDATE_DIR')
        if not selected:
            self.skipTest('No privately copied Totori DX decrypted PS4 export supplied.')
        root = Path(selected)
        files = tuple(path for path in root.rglob('USR-DATA*') if path.is_file()
                      and path.stat().st_size == candidate.SAVE_SIZE)
        self.assertTrue(files, 'No qualified-size Totori PS4 gameplay copies found.')
        self.assertLessEqual(len(files), 99)
        for path in files:
            with self.subTest(copy=path.name):
                with path.open('rb') as stream:
                    raw = stream.read(candidate.SAVE_SIZE + 1)
                companion = path.parent / 'sce_sys' / 'param.sfo'
                with companion.open('rb') as stream:
                    metadata = stream.read(candidate.MAX_SFO_SIZE + 1)
                document = candidate.inspect(raw, metadata)
                self.assertEqual(candidate.unchanged(document), raw)
                self.assertEqual(tuple(item.stored_id for item in document.characters), tuple(range(10)))
                self.assertTrue(all(item.canonical_empty or item.ordinary_shape for item in document.items))
                self.assertFalse(document.integrity_qualified)
                if path.name == 'USR-DATA.dat':
                    preview = re.search(rb'Money:(\d+)Cole', metadata)
                    self.assertIsNotNone(preview)
                    self.assertEqual(document.cole, int(preview[1]))
                    self.assertTrue(all(document.characters[index].stored_level == 50 for index in (0, 2, 6)))


if __name__ == '__main__':
    unittest.main()
