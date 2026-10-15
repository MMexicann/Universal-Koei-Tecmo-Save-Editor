"""Read-only proficiency qualification and preservation; no game execution."""
from dataclasses import FrozenInstanceError, replace
from functools import lru_cache
import os
from pathlib import Path
import struct
import unittest

from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.origins import origins_codec as codec
from koei_editor.games.origins import origins_parser as backend
from koei_editor.games.origins.origins_proficiency import proficiency_records
from tests.test_origins_parser import fixture


BASES = {16: 0x7f8d, 17: 0x7f8d, 29: 0x8055}


@lru_cache(maxsize=3)
def proficiency_fixture(revision=29):
    """Generate record topology independently of the implementation constants."""
    original = backend.decode(fixture(revision))
    payload = bytearray(original.payload)
    base = BASES[revision]
    for index in range(50):
        struct.pack_into('<I4H2B', payload, base + index * 14,
                         0, 0xffff, 0xffff, 0xffff, 0xffff, 0xa6, 0xb7)
    for index in range(12 if revision == 29 else 10):
        struct.pack_into('<I4H2B', payload, base + index * 14,
                         1000 + index * 7, index * 20, index * 20 + 1,
                         408, 0xffff, index, 255 - index)
    return codec.encode(bytes(payload), original.seed, 'slot')


def changed_record(revision, offset, raw):
    document = backend.decode(proficiency_fixture(revision))
    payload = bytearray(document.payload)
    payload[offset:offset + len(raw)] = raw
    return backend.decode(codec.encode(bytes(payload), document.seed, 'slot'))


class OriginsProficiencyTests(unittest.TestCase):
    def test_all_revisions_names_ids_empty_sentinel_and_opaque_state(self):
        for revision in (16, 17, 29):
            with self.subTest(revision=revision):
                document = backend.decode(proficiency_fixture(revision))
                rows = proficiency_records(document)
                self.assertEqual(len(rows), 12 if revision == 29 else 10)
                self.assertEqual(rows[0].offset, BASES[revision])
                sword = rows[2]
                self.assertEqual((sword.index, sword.family, sword.stored_xp),
                                 (2, 'Sword', 1014))
                self.assertEqual(sword.battle_arts, (40, 41, 408, None))
                self.assertEqual(sword.unmapped_state, b'\x02\xfd')
                self.assertEqual(rows[9].family, 'Halberd')
                if revision == 29:
                    self.assertEqual(rows[10].family, 'Bow')
                    self.assertEqual(rows[11].family, 'Family ID 11')
                with self.assertRaises(FrozenInstanceError):
                    sword.stored_xp = 0
                self.assertEqual(backend.serialize(document, {}), document.raw)

    def test_unusual_xp_and_reserved_bytes_are_preserved_without_level_inference(self):
        document = changed_record(29, BASES[29] + 2 * 14, b'\xff' * 4)
        document = self._change(document, BASES[29] + 12 * 14, b'\xc3' * (38 * 14))
        rows = proficiency_records(document)
        self.assertEqual(len(rows), 12)
        self.assertEqual(rows[2].stored_xp, 0xffffffff)
        self.assertFalse(hasattr(rows[2], 'level'))
        self.assertFalse(hasattr(rows[2], 'owned'))
        edited = backend.decode(backend.serialize(document, {'gold': 2345}))
        start, end = BASES[29], BASES[29] + 700
        self.assertEqual(edited.payload[start:end], document.payload[start:end])
        self.assertEqual(proficiency_records(edited), rows)

    @staticmethod
    def _change(document, offset, raw):
        payload = bytearray(document.payload)
        payload[offset:offset + len(raw)] = raw
        return backend.decode(codec.encode(bytes(payload), document.seed, 'slot'))

    def test_unfamiliar_art_shape_withholds_optional_view_without_blocking_resources(self):
        document = backend.decode(proficiency_fixture(17))
        offset = BASES[17] + 2 * 14 + 4
        for arts in ((0, 1, 408, 0xffff), (40, 41, 999, 1000),
                     (400, 401, 408, 0xffff)):
            with self.subTest(arts=arts):
                unfamiliar = self._change(document, offset, struct.pack('<4H', *arts))
                self.assertEqual(proficiency_records(unfamiliar), ())
                self.assertEqual(backend.serialize(unfamiliar, {}), unfamiliar.raw)
                output = backend.decode(backend.serialize(unfamiliar, {'gold': 2345}))
                self.assertEqual(backend.field_map(output)['gold'].value(output.payload), 2345)
                self.assertEqual(output.payload[BASES[17]:BASES[17] + 700],
                                 unfamiliar.payload[BASES[17]:BASES[17] + 700])
        self.assertEqual(proficiency_records(backend.decode(fixture(29))), ())

    def test_optional_dlc_rows_and_unowned_formed_records_do_not_grant_ownership(self):
        document = backend.decode(proficiency_fixture(29))
        empty = struct.pack('<I4H2B', 0, 0xffff, 0xffff, 0xffff, 0xffff, 0, 255)
        document = self._change(document, BASES[29] + 10 * 14, empty * 2)
        for index in range(10):
            document = self._change(document, BASES[29] + index * 14 + 12, b'\x00\xff')
        rows = proficiency_records(document)
        self.assertEqual(len(rows), 10)
        self.assertTrue(all(row.unmapped_state == b'\x00\xff' for row in rows))

    def test_forged_documents_and_field_writes_are_refused(self):
        document = backend.decode(proficiency_fixture(29))
        for fake in (None, object(), replace(document, revision=17),
                     replace(document, payload=document.payload[:-1]),
                     replace(document, raw=bytearray(document.raw)),
                     replace(document, format=replace(document.format))):
            with self.subTest(type=type(fake).__name__), self.assertRaises(SaveError):
                proficiency_records(fake)
        adapter = get_game('origins').get_scalar_adapter()
        fields = adapter.fields_for(document)
        self.assertFalse(any('proficiency' in field.id or 'battle_art' in field.id
                             for field in fields))
        for key in ('proficiency_2_xp', 'proficiency_2_level', 'battle_art_2_0'):
            with self.subTest(field=key), self.assertRaises(SaveError):
                adapter.stage(document, {}, key, 100)
            with self.assertRaises(SaveError):
                adapter.serialize(document, {key: 100})

    def test_independent_native_slots_when_supplied(self):
        value = os.environ.get('ORIGINS_PROFICIENCY_SAVE_COPIES')
        if not value:
            self.skipTest('Set ORIGINS_PROFICIENCY_SAVE_COPIES to separate native slot copies.')
        paths = tuple(Path(item) for item in value.split(os.pathsep) if item)
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(slot=path.name):
                original = path.read_bytes()
                document = backend.read_save(path)
                rows = proficiency_records(document)
                self.assertGreaterEqual(len(rows), 10)
                self.assertEqual(rows[2].family, 'Sword')
                self.assertEqual(rows[9].family, 'Halberd')
                for row in rows:
                    self.assertEqual(row.stored_xp,
                                     int.from_bytes(document.payload[row.offset:row.offset + 4], 'little'))
                    self.assertEqual(row.unmapped_state,
                                     document.payload[row.offset + 12:row.offset + 14])
                self.assertEqual(backend.serialize(document, {}), original)
                gold = backend.field_map(document)['gold'].value(document.payload)
                edited = backend.decode(backend.serialize(document, {'gold': 1 if gold != 1 else 2}))
                self.assertEqual(proficiency_records(edited), rows)
                self.assertEqual(path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
