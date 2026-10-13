"""Independent procedural records; public mod reference is not a player save."""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.games.bandit_kings_mac import parser
from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.adapter_contract import BoundScalarAdapter


def procedural_raw():
    raw = bytearray((index * 31 + 17) % 256 for index in range(parser.SIZE))
    raw[:4] = b'SUI1'
    raw[parser.SETUP_START:parser.SETUP_START + 3] = (1115).to_bytes(2, 'big') + b'\x07'
    for index in range(parser.HERO_COUNT):
        base = parser.HERO_START + index * parser.HERO_STRIDE
        raw[base + 23] &= 0x7F
        name = b'Gao Qiu' if index == 0 else f'Hero {index}'.encode()
        off = parser.NAMES_START + index * parser.NAMES_STRIDE
        raw[off:off + 16] = name.ljust(16, b'\0')
    for index in range(parser.PREFECTURE_COUNT):
        base = parser.PREFECTURE_START + index * parser.PREFECTURE_STRIDE
        raw[base + 31] = 0
        name = b'Lan' if index == 0 else f'Pref {index}'.encode()
        off = parser.TACTICAL_START + index * parser.TACTICAL_STRIDE
        raw[off:off + 10] = name.ljust(10, b'\0')
    for index in (0, 254):
        base = parser.HERO_START + index * parser.HERO_STRIDE
        raw[base + 5:base + 7] = bytes((index, 0 if index == 0 else 48))
        raw[base + 23] |= 0x80
        raw[base + 12:base + 15] = bytes((83, 77, 254))
        pref = parser.PREFECTURE_START + (0 if index == 0 else 48) * parser.PREFECTURE_STRIDE
        raw[pref + 31] = index + 1
        for relative in (12, 14, 16, 18):
            raw[pref + relative:pref + relative + 2] = (54321 + relative).to_bytes(2, 'big')
    return bytes(raw)


class BanditKingsMacTests(unittest.TestCase):
    def setUp(self):
        self.adapter = BoundScalarAdapter(parser.GAME_ID, '.cim', parser)
        self.raw = procedural_raw()
        self.document = self.adapter.decode(self.raw)

    def test_noop_qualification_and_existing_gates(self):
        self.assertEqual(self.adapter.serialize(self.document, {}), self.raw)
        self.assertTrue(self.document.format.published_format)
        self.assertFalse(self.document.format.sample_verified)
        self.assertFalse(self.document.format.game_load_verified)
        self.assertEqual(len(self.adapter.fields_for(self.document)), 14)
        self.assertNotIn('hero_1_strength', parser.field_map(self.document))
        self.assertNotIn('prefecture_1_gold', parser.field_map(self.document))
        self.assertEqual(len(parser.hero_records(self.document)), 2)
        self.assertEqual(len(parser.prefecture_records(self.document)), 49)

    def test_all_fields_surgical_be_readback_and_immutable_stage(self):
        for field in self.adapter.fields_for(self.document):
            original = field.value(self.document.payload)
            pending = {}
            changes = self.adapter.stage(self.document, pending, field.id, 7)
            self.assertEqual(pending, {})
            self.assertEqual(self.adapter.stage(self.document, changes, field.id, original), {})
            self.assertEqual(changes, {field.id: 7})
            output = self.adapter.serialize(self.document, changes)
            changed = {i for i, pair in enumerate(zip(output, self.raw)) if pair[0] != pair[1]}
            self.assertLessEqual(changed, set(range(field.offset, field.offset + field.size)))
            self.assertEqual(output[field.offset:field.offset + field.size], (7).to_bytes(field.size, 'big'))
            self.assertEqual(parser.field_map(self.adapter.decode(output))[field.id].value(output), 7)
            self.assertEqual(self.adapter.maximums(self.document, changes), changes)
            self.assertEqual(self.adapter.limit_values(self.document, changes, [field.id]), {})
            self.assertEqual(len(self.adapter.review(self.document, changes)), 1)
        self.assertEqual(self.document.raw, self.raw)

    def test_invalid_pending_types_snapshot_and_unusual_opened_value(self):
        key = 'hero_0_wisdom'
        changes = self.adapter.stage(self.document, {}, key, 12)
        self.assertEqual(self.adapter.stage(self.document, changes, key, 254), {})
        for value in (-1, 255, True, 254.0, '254', None):
            with self.subTest(value=value), self.assertRaises(SaveError):
                self.adapter.stage(self.document, {}, key, value)
        for pending in ({'unknown': 1}, {key: True}, [], None):
            with self.assertRaises(SaveError):
                self.adapter.serialize(self.document, pending)
        for forged in (replace(self.document, payload=b'x' * parser.SIZE),
                       replace(self.document, source=None),
                       replace(self.document, format=replace(parser.FORMAT)),
                       replace(self.document, raw=bytearray(self.raw))):
            with self.assertRaises(SaveError):
                self.adapter.serialize(forged, {})

    def test_geometry_identity_calendar_and_native_reference_links(self):
        for raw in (self.raw[:-1], self.raw + b'x', b'\0' * parser.SIZE, memoryview(self.raw)):
            with self.assertRaises(SaveError):
                self.adapter.decode(raw)
        for offset, value in ((0, 0), (parser.SETUP_START + 2, 13),
                              (parser.HERO_START + 6, 49), (parser.HERO_START + 5, 1),
                              (parser.NAMES_START, 0), (parser.TACTICAL_START, 0)):
            raw = bytearray(self.raw); raw[offset] = value
            with self.subTest(offset=offset), self.assertRaises(SaveError):
                self.adapter.decode(raw)
        with self.assertRaises(SaveError):
            parser.decode(self.raw, 'bandit_kings_nes')

    def test_safe_copies_backups_restore_source_race_and_disk_readback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'copy.cim'; source.write_bytes(self.raw)
            document = self.adapter.read_save(source)
            field = self.adapter.fields_for(document)[0]
            target = root / 'edited.cim'
            saved = self.adapter.save_as(document, {field.id: 0}, target)
            self.assertEqual(source.read_bytes(), self.raw)
            self.assertEqual(saved.raw, target.read_bytes())
            backup = self.adapter.backup(document)
            restored = root / 'restored.cim'; self.adapter.restore(backup, restored)
            self.assertEqual(restored.read_bytes(), self.raw)
            with self.assertRaises(FileExistsError):
                self.adapter.save_as(document, {}, target)
            real_backup = parser.backup
            def raced_backup(doc):
                result = real_backup(doc)
                source.write_bytes(self.raw[:-1] + bytes((self.raw[-1] ^ 1,)))
                return result
            with patch.object(parser, 'backup', side_effect=raced_backup), self.assertRaises(SaveError):
                self.adapter.save_as(document, {}, root / 'race.cim')
            self.assertFalse((root / 'race.cim').exists())
            source.write_bytes(self.raw)
            (root / 'SUIDATA2.CIM').write_bytes(b'x')
            with self.assertRaises(SaveError):
                self.adapter.read_save(source)

    def test_optional_public_modified_scenario_geometry(self):
        path = os.environ.get('BANDIT_KINGS_MAC_REFERENCE_COPY')
        if not path:
            self.skipTest('Optional source modified scenario; not a native saved campaign.')
        raw = Path(path).read_bytes()
        document = parser.decode(raw)
        self.assertEqual(parser.serialize(document, {}), raw)
        for field in parser.fields_for(document):
            output = parser.serialize(document, {field.id: 0})
            changed = {i for i, (a, b) in enumerate(zip(raw, output)) if a != b}
            self.assertLessEqual(changed, set(range(field.offset, field.offset + field.size)))


if __name__ == '__main__':
    unittest.main()
