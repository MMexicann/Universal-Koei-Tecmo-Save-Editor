"""Procedural native-format and optional public modified player-export tests.

No console game-load validation. Private fixtures are never bundled/published.
"""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.fire_emblem_warriors import parser as fe
from koei_editor.games.fire_emblem_warriors.catalog import MATERIALS


def procedural_fe():
    b = bytearray((i * 13 + 29) & 255 for i in range(fe.SAVE_SIZE))
    b[:4] = fe.LAYOUT_MARKER
    b[4:8] = fe.SAVE_SIZE.to_bytes(4, 'little')
    for offset, _ in MATERIALS:
        b[offset:offset + 2] = bytes(2)
    b[0x2C:0x2E] = (10).to_bytes(2, 'little')
    b[0x2E:0x30] = (1001).to_bytes(2, 'little')
    b[0xE8:0xEA] = (1).to_bytes(2, 'little')  # Scroll, never editable.
    b[fe.GOLD_OFFSET:fe.GOLD_OFFSET + 4] = (500).to_bytes(4, 'little')
    empty = bytes(16) + b'\xff' * 10 + bytes(4) + b'\xff\xff'
    b[fe.WEAPON_OFFSET:] = empty * fe.WEAPON_COUNT
    for i, identity, stars in ((0, 4, 2), (1, 0x1234, 1), (2, 4, 7)):
        o = fe.WEAPON_OFFSET + i * fe.WEAPON_STRIDE
        b[o + 24:o + 26] = identity.to_bytes(2, 'little')
        b[o + 26] = stars
    o = fe.WEAPON_OFFSET
    b[o:o + 2] = (1000).to_bytes(2, 'little')
    b[o + 16] = 28
    b[o + 2:o + 4] = (10000).to_bytes(2, 'little')
    b[o + 17] = 34  # True Power is prerequisite-sensitive.
    b[o + 4:o + 6] = (25000).to_bytes(2, 'little')
    b[o + 18] = 55  # Legendary prerequisite-sensitive.
    return bytes(b)


class FireEmblemFormatTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.source = Path(self.folder.name) / 'scenario0'
        self.raw = procedural_fe()
        self.source.write_bytes(self.raw)
        self.doc = fe.read_save(self.source)

    def test_byte_exact_roundtrip_header_and_invalid_inputs(self):
        self.assertEqual(fe.serialize(self.doc, {}), self.raw)
        for b in (self.raw[:-1], self.raw + b'\0', b'\0' * len(self.raw),
                  self.raw[:4] + bytes(4) + self.raw[8:]):
            with self.assertRaises(SaveError): fe.decode(b)
        with self.assertRaises(SaveError): fe.decode(self.raw, 'fire_emblem_warriors_3ds')
        with self.assertRaises(SaveError): fe.serialize(replace(self.doc, payload=bytearray(self.raw)), {})
        with self.assertRaises(SaveError): fe.serialize(replace(self.doc, payload=self.raw[:-1] + b'\0'), {})

    def test_ordinary_material_qualification_and_special_reward_preservation(self):
        fields = fe.field_map(self.doc)
        self.assertIn('material_44', fields)
        self.assertNotIn('material_48', fields)  # Unowned or exhausted.
        for offset, name in MATERIALS:
            if not fe._ordinary(name): self.assertNotIn(f'material_{offset}', fields)
        edits = fe.maximums(self.doc, {})
        self.assertNotIn('material_44', edits)
        self.assertNotIn('gold', edits)
        self.assertEqual(fe.stage(self.doc, {}, 'material_44', 999), {'material_44': 999})
        self.assertNotIn('material_46', edits)
        self.assertNotIn('weapon_3_stars', edits)  # Higher originals preserved.
        output = fe.serialize(self.doc, edits)
        self.assertEqual(output[:40], self.raw[:40])
        self.assertEqual(output[0xE8:0xEA], self.raw[0xE8:0xEA])
        self.assertEqual(fe.stage(self.doc, {'material_46': 20}, 'material_46', 1001), {})

    def test_surgical_stars_and_decrease_only_seals(self):
        fields = fe.field_map(self.doc)
        self.assertNotIn('weapon_2_stars', fields)
        self.assertIn('weapon_1_seal_1_kos', fields)
        self.assertNotIn('weapon_1_seal_2_kos', fields)
        self.assertNotIn('weapon_1_seal_3_kos', fields)
        changes = fe.stage(self.doc, {}, 'weapon_1_seal_1_kos', 0)
        changes = fe.stage(self.doc, changes, 'weapon_1_stars', 5)
        result = fe.serialize(self.doc, changes)
        allowed = {fe.WEAPON_OFFSET, fe.WEAPON_OFFSET + 1, fe.WEAPON_OFFSET + 26}
        self.assertLessEqual({i for i, (x, y) in enumerate(zip(self.raw, result)) if x != y}, allowed)
        self.assertNotIn('weapon_1_seal_1_kos', fe.maximums(self.doc, {}))
        with self.assertRaises(SaveError): fe.stage(self.doc, {}, 'weapon_1_seal_1_kos', 1001)
        with self.assertRaises(SaveError): fe.stage(self.doc, {}, 'weapon_1_stars', 6)

    def test_seal_natural_caps_and_nonsealed_attribute_exclusions(self):
        for identity, count, eligible in ((23, 2000, True), (23, 2001, True),
                (37, 3000, True), (37, 3001, True), (38, 2500, True),
                (47, 4000, True), (48, 4001, True), (1, 1000, False),
                (35, 1000, False), (46, 1000, False), (34, 1000, False),
                (55, 1000, False)):
            raw = bytearray(self.raw)
            raw[fe.WEAPON_OFFSET:fe.WEAPON_OFFSET + 2] = count.to_bytes(2, 'little')
            raw[fe.WEAPON_OFFSET + 16] = identity
            fields = fe.field_map(fe.decode(raw))
            self.assertEqual('weapon_1_seal_1_kos' in fields, eligible, identity)

    def test_every_pending_edit_validated_before_max(self):
        for changes in ({'gold': True}, {'gold': -1}, {'gold': '10'}, {'unknown': 1}, {'gold': 10_000_000}):
            with self.assertRaises(SaveError): fe.maximums(self.doc, changes)
            with self.assertRaises(SaveError): fe.limit_values(self.doc, changes, ['gold'])
            with self.assertRaises(SaveError): fe.serialize(self.doc, changes)

    def test_safe_new_copy_backup_restore_and_source_guard(self):
        dest = self.source.with_name('edited')
        fe.save_as(self.doc, {'gold': 321}, dest)
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertEqual(fe.field_map(fe.read_save(dest))['gold'].value(dest.read_bytes()), 321)
        backup = next(p for p in (self.source.parent / 'WarriorsEditorBackups').iterdir() if p.suffix != '.json')
        restored = fe.restore(backup, self.source.with_name('restored'))
        self.assertEqual(restored.read_bytes(), self.raw)
        with self.assertRaises(FileExistsError): fe.save_as(self.doc, {}, dest)
        with self.assertRaises(SaveError): fe.save_as(self.doc, {}, self.source.with_name('wrong.bin'))
        self.source.write_bytes(self.raw[:100] + b'x' + self.raw[101:])
        with self.assertRaises(SaveError): fe.save_as(self.doc, {}, self.source.with_name('changed'))

    def test_unknown_and_higher_weapon_records_preserved(self):
        edits = fe.maximums(self.doc, {})
        result = fe.serialize(self.doc, edits)
        o = fe.WEAPON_OFFSET + fe.WEAPON_STRIDE
        self.assertEqual(result[o:o + 2 * fe.WEAPON_STRIDE], self.raw[o:o + 2 * fe.WEAPON_STRIDE])
        self.assertEqual(len(fe.weapons(self.doc)), 3)
        self.assertEqual(len(fe.inspection_rows(self.doc)), len(MATERIALS) + 64)

    @unittest.skipUnless(os.environ.get('FE_WARRIORS_SAVE_COPY'), 'No private genuine modified player native export')
    def test_public_modified_player_export_roundtrip_and_each_field(self):
        raw = Path(os.environ['FE_WARRIORS_SAVE_COPY']).read_bytes()
        document = fe.decode(raw)
        self.assertEqual(fe.serialize(document, {}), raw)
        fields = fe.fields_for(document)
        self.assertGreater(len(fields), 100)
        self.assertEqual(len(fe.weapons(document)), 49)
        for field in fields:
            old = field.value(raw)
            value = min(field.maximum, max(field.minimum, old - 1))
            result = fe.serialize(document, fe.stage(document, {}, field.id, value))
            self.assertLessEqual({i for i, (a, b) in enumerate(zip(raw, result)) if a != b},
                                 set(range(field.offset, field.offset + field.size)))
            parsed = fe.decode(result)
            self.assertEqual(field.value(parsed.payload), value)
        self.assertEqual(Path(os.environ['FE_WARRIORS_SAVE_COPY']).read_bytes(), raw)
