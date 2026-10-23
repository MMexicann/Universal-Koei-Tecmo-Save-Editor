"""Procedural robustness tests, plus an optional private genuine native copy.

Procedural bytes are test data, not a player save or game-load validation.
"""
from dataclasses import replace
import os
from pathlib import Path
import random
import struct
import tempfile
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.shared.koei_codec import word_sum
from koei_editor.games.origins.origins_codec import word_cipher
import koei_editor.games.sw4dx.samurai4dx_codec as codec
import koei_editor.games.sw4dx.samurai4dx_parser as parser


def seal(payload, seed=34277, header=None):
    payload = bytearray(payload)
    for offset, checksum in zip(codec.CHECKSUM_OFFSETS, codec.checksums(payload)):
        struct.pack_into('<I', payload, offset, checksum)
    header = bytes(codec.PAYLOAD_OFFSET - 4) if header is None else header
    return header + struct.pack('<HH', word_sum(payload), seed) + word_cipher(bytes(payload), seed)


def procedural_raw():
    rng = random.Random(41104)
    payload = bytearray(rng.randbytes(codec.PAYLOAD_SIZE))
    struct.pack_into('<I', payload, 0, codec.REVISION)
    for i in range(parser.OFFICER_COUNT):
        base = parser.OFFICER_BASE + i * parser.OFFICER_STRIDE
        struct.pack_into('<I', payload, base, i)
        payload[base + 0x3B] = 0
        payload[base + 0x3F] = 0xA0  # Unknown flag bits must survive unlocking.
    for i in range(parser.WEAPON_OWNERS * parser.WEAPON_SLOTS):
        base = parser.WEAPON_BASE + i * parser.WEAPON_STRIDE
        struct.pack_into('<H', payload, base, 180)
        payload[base + 2:base + 10] = bytes(8)
        payload[base + 10:base + 18] = bytes([40]) * 8
    for owner in range(parser.OFFICER_COUNT):
        struct.pack_into('<H', payload, parser.WEAPON_BASE + owner * 8 * parser.WEAPON_STRIDE,
                         owner * 2)
    for slot in (0, 1):
        base = parser.WEAPON_BASE + slot * parser.WEAPON_STRIDE
        struct.pack_into('<H', payload, base, slot)
        payload[base + 2] = 5
        payload[base + 10] = 21  # Blaze; existing attached skill.
        payload[base + 18] = 1
        payload[base + 26] = 0xA1  # Locked; unrelated flags present.
    struct.pack_into('<I', payload, parser.GOLD_OFFSET, 1234)
    payload[parser.GEM_BASE:parser.GEM_BASE + 8] = bytes(range(8))
    return seal(payload, header=rng.randbytes(codec.PAYLOAD_OFFSET - 4))


class Samurai4DXTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = procedural_raw()
        cls.document = parser.decode(cls.raw)

    def test_unchanged_roundtrip(self):
        self.assertEqual(parser.serialize(self.document, {}), self.raw)
        self.assertEqual(parser.decode(self.raw).seed, 34277)

    def test_native_integrity_and_surgical_edit(self):
        changes = {'gold': 999999, 'gem_3': 99, 'officer_2_attack': 315,
                   'officer_0_unlocked': 1, 'officer_0_equipped_weapon': 1,
                   'weapon_0_0_skill_0_rank': 5, 'weapon_0_0_skill_0_active': 1}
        raw = parser.serialize(self.document, changes)
        edited = parser.decode(raw)
        expected = parser.changed_payload(self.document, changes)
        allowed = set()
        for field in parser.field_map(self.document).values():
            if field.id in changes:
                allowed.update(range(field.offset, field.offset + field.size))
        allowed.add(parser.WEAPON_BASE + 0x1A)
        for offset in codec.CHECKSUM_OFFSETS:
            allowed.update(range(offset, offset + 4))
        differences = {i for i, (a, b) in enumerate(zip(self.document.payload, edited.payload)) if a != b}
        self.assertTrue(differences <= allowed)
        for offset in codec.CHECKSUM_OFFSETS:
            expected = expected[:offset] + edited.payload[offset:offset + 4] + expected[offset + 4:]
        self.assertEqual(edited.payload, expected)
        self.assertEqual(raw[:codec.PAYLOAD_OFFSET - 4], self.raw[:codec.PAYLOAD_OFFSET - 4])
        self.assertEqual(edited.seed, self.document.seed)
        self.assertEqual(edited.payload[parser.OFFICER_BASE + 0x3F], 0xA5)
        self.assertEqual(edited.payload[parser.WEAPON_BASE + 0x1A], 0xA2)

    def test_direct_serializer_preserves_exact_unusual_opened_values(self):
        payload = bytearray(self.document.payload)
        struct.pack_into('<I', payload, parser.GOLD_OFFSET, 1000001)
        payload[parser.GEM_BASE] = 150
        raw = seal(payload, seed=codec.decode_envelope(self.raw)[1],
                   header=self.raw[:codec.PAYLOAD_OFFSET - 4])
        document = parser.decode(raw)
        opened_payload = document.payload
        changes = {'gold': 1000001, 'gem_0': 150, 'officer_0_unlocked': 0}
        self.assertEqual(parser.changed_payload(document, changes), opened_payload)
        self.assertEqual(parser.serialize(document, changes), raw)
        self.assertEqual(document.raw, raw)
        self.assertEqual(document.payload, opened_payload)
        self.assertEqual(document.payload[parser.OFFICER_BASE + 0x3F], 0xA0)

    def test_direct_serializer_keeps_an_opened_locked_officer_locked(self):
        field = parser.field_map(self.document)['officer_0_unlocked']
        self.assertEqual(field.value(self.document.payload), 0)
        self.assertEqual(self.document.payload[field.offset], 0xA0)
        self.assertEqual(parser.changed_payload(self.document, {field.id: 0}),
                         self.document.payload)
        self.assertEqual(parser.serialize(self.document, {field.id: 0}), self.raw)

    def test_direct_serializer_allows_edits_alongside_unusual_opened_noops(self):
        payload = bytearray(self.document.payload)
        struct.pack_into('<I', payload, parser.GOLD_OFFSET, 1000001)
        payload[parser.GEM_BASE] = 150
        raw = seal(payload)
        document = parser.decode(raw)
        edited = parser.decode(parser.serialize(document, {
            'gold': 1000001, 'gem_0': 150, 'gem_1': 5,
            'officer_0_unlocked': 0}))
        self.assertEqual(parser.field_map(edited)['gem_1'].value(edited.payload), 5)
        self.assertEqual(parser.field_map(edited)['gold'].value(edited.payload), 1000001)
        self.assertEqual(parser.field_map(edited)['gem_0'].value(edited.payload), 150)
        allowed = {parser.GEM_BASE + 1}
        for offset in codec.CHECKSUM_OFFSETS:
            allowed.update(range(offset, offset + 4))
        touched = {i for i, (before, after) in enumerate(zip(document.payload, edited.payload))
                   if before != after}
        self.assertEqual(touched - allowed, set())
        self.assertEqual(document.raw, raw)
        self.assertEqual(edited.seed, document.seed)
        self.assertEqual(edited.raw[:codec.PAYLOAD_OFFSET - 4], raw[:codec.PAYLOAD_OFFSET - 4])

    def test_direct_opened_noop_does_not_admit_new_invalid_values_or_types(self):
        payload = bytearray(self.document.payload)
        struct.pack_into('<I', payload, parser.GOLD_OFFSET, 1000001)
        payload[parser.GEM_BASE] = 150
        document = parser.decode(seal(payload))
        for changes in ({'gold': 1000002}, {'gem_0': 151},
                        {'gold': True}, {'gold': 1000001.0},
                        {'gem_0': 150.0}, {'officer_0_unlocked': False},
                        {'unmapped': 0}):
            with self.subTest(changes=changes), self.assertRaises(SaveError):
                parser.serialize(document, changes)
        self.assertEqual(document.payload[parser.GEM_BASE], 150)

    def test_unknown_bytes_empty_records_and_higher_values(self):
        payload = bytearray(self.document.payload)
        struct.pack_into('<I', payload, parser.GOLD_OFFSET, 1000001)
        payload[parser.GEM_BASE] = 150
        payload[parser.WEAPON_BASE + 0x12] = 9
        doc = parser.decode(seal(payload))
        changes = parser.maximums(doc, {})
        self.assertNotIn('gold', changes)
        self.assertNotIn('gem_0', changes)
        self.assertNotIn('weapon_0_0_skill_0_rank', changes)
        self.assertFalse(any(k.endswith('_active') or k.endswith('_attack') for k in changes))
        self.assertNotIn('weapon_0_2_skill_0_rank', parser.field_map(doc))
        self.assertEqual(doc.payload[parser.WEAPON_BASE + 0x12], 9)
        # Activating a skill preserves every flag other than the lock bit.
        edited = parser.decode(parser.serialize(doc, {'weapon_0_0_skill_0_active': 1}))
        self.assertEqual(edited.payload[parser.WEAPON_BASE + 0x1A], 0xA0)
        self.assertEqual(edited.payload[parser.WEAPON_BASE + 0x12], 9)
        payload[parser.WEAPON_BASE + 0x12] = 0
        zero = parser.decode(seal(payload))
        self.assertNotIn('weapon_0_0_skill_0_rank', parser.field_map(zero))
        self.assertNotIn('weapon_0_0_skill_0_active', parser.field_map(zero))
        self.assertNotIn('weapon_0_0_skill_0_rank', parser.maximums(zero, {}, 'Weapons'))

    def test_max_preserves_locked_state_and_ceilings(self):
        changes = parser.maximums(self.document, {}, 'Weapons')
        edited = parser.decode(parser.serialize(self.document, changes))
        self.assertEqual(edited.payload[parser.WEAPON_BASE + 2], 5)
        self.assertEqual(edited.payload[parser.WEAPON_BASE + 0x12], 5)
        self.assertEqual(edited.payload[parser.WEAPON_BASE + 0x1A], 0xA3)
        lower = parser.decode(parser.serialize(edited, {'weapon_0_0_skill_0_rank': 3}))
        self.assertEqual(lower.payload[parser.WEAPON_BASE + 0x1A], 0xA3)

    def test_bounds_dependencies_and_identity(self):
        for key, value in [('gold', 1000000), ('gem_0', 100), ('officer_0_attack', -1),
                           ('weapon_0_0_skill_0_rank', 6), ('gold', True),
                           ('unknown', 1)]:
            with self.subTest(key=key, value=value), self.assertRaises(SaveError):
                parser.stage(self.document, {}, key, value)
        with self.assertRaises(SaveError):
            parser.serialize(self.document, {'officer_0_equipped_weapon': 2})
        with self.assertRaises(SaveError):
            parser.stage(self.document, {}, 'officer_0_equipped_weapon', 2)
        unlocked = parser.decode(parser.serialize(self.document, {'officer_0_unlocked': 1}))
        with self.assertRaises(SaveError):
            parser.stage(unlocked, {}, 'officer_0_unlocked', 0)
        self.assertEqual(parser.stage(self.document, {'officer_0_unlocked': 1},
                                      'officer_0_unlocked', 0), {})
        with self.assertRaises(SaveError):
            parser.validate_document(replace(self.document, seed=1))
        with self.assertRaises(SaveError):
            parser.validate_document(replace(self.document, payload=bytes(codec.PAYLOAD_SIZE)))
        for attribute, value in [('raw', bytearray(self.raw)),
                                 ('payload', bytearray(self.document.payload)), ('seed', True)]:
            with self.assertRaises(SaveError):
                parser.validate_document(replace(self.document, **{attribute: value}))
        with self.assertRaises(SaveError):
            parser.decode(self.raw, 'sw5')

    def test_corruption_and_foreign_revision_rejected(self):
        for length in [0, codec.SAVE_SIZE - 1, codec.SAVE_SIZE + 1]:
            with self.assertRaises(SaveError):
                parser.decode(bytes(length))
        damaged = bytearray(self.raw)
        damaged[codec.PAYLOAD_OFFSET + 500] ^= 1
        with self.assertRaisesRegex(SaveError, 'envelope checksum'):
            parser.decode(damaged)
        payload = bytearray(self.document.payload)
        payload[codec.CHECKSUM_OFFSETS[0]] ^= 1
        envelope_only = (self.raw[:codec.PAYLOAD_OFFSET - 4] + struct.pack('<HH', word_sum(payload), 34277)
                         + word_cipher(bytes(payload), 34277))
        with self.assertRaisesRegex(SaveError, 'section checksum'):
            parser.decode(envelope_only)
        struct.pack_into('<I', payload, 0, 0x35C7)
        with self.assertRaisesRegex(SaveError, 'revision'):
            parser.decode(seal(payload))
        payload = bytearray(self.document.payload)
        struct.pack_into('<I', payload, parser.OFFICER_BASE, 99)
        with self.assertRaisesRegex(SaveError, 'identities'):
            parser.decode(seal(payload))

    def test_unstage_review_and_inspection(self):
        staged = parser.stage(self.document, {}, 'gold', 999999)
        self.assertEqual(parser.stage(self.document, staged, 'gold', 1234), {})
        review = parser.review(self.document, staged)
        self.assertEqual([(f.id, old, new) for f, old, new in review], [('gold', 1234, 999999)])
        rows = parser.inspection_rows(self.document)
        self.assertTrue(any('Blaze' in row['value'] for row in rows))
        self.assertTrue(any('Level' in row['value'] for row in rows))
        payload = bytearray(self.document.payload)
        struct.pack_into('<H', payload, parser.WEAPON_BASE, 180)
        absent = parser.decode(seal(payload))
        self.assertNotIn('officer_0_unlocked', parser.field_map(absent))

    def test_save_backup_restore_source_and_overwrite_guards(self):
        with tempfile.TemporaryDirectory() as folder:
            source, destination = Path(folder) / 'source.dat', Path(folder) / 'edited.dat'
            source.write_bytes(self.raw)
            doc = parser.read_save(source)
            edited = parser.save_as(doc, {'gold': 5000}, destination)
            self.assertEqual(source.read_bytes(), self.raw)
            self.assertEqual(parser.field_map(edited)['gold'].value(edited.payload), 5000)
            backups = list((Path(folder) / 'WarriorsEditorBackups').glob('*.dat'))
            self.assertEqual(len(backups), 1)
            restored = Path(folder) / 'restored.dat'
            parser.restore(backups[0], restored)
            self.assertEqual(restored.read_bytes(), self.raw)
            with self.assertRaises(FileExistsError):
                parser.save_as(doc, {}, destination)
            source.write_bytes(bytes(len(self.raw)))
            with self.assertRaisesRegex(SaveError, 'changed on disk'):
                parser.save_as(doc, {}, Path(folder) / 'other.dat')


@unittest.skipUnless(os.environ.get('SW4DX_SAVE_COPY'), 'Private genuine SW4 DX save copy not supplied')
class GenuineSamurai4DXTests(unittest.TestCase):
    def test_native_copy_roundtrip_and_targeted_edit(self):
        raw = Path(os.environ['SW4DX_SAVE_COPY']).read_bytes()
        document = parser.decode(raw)
        self.assertEqual(parser.serialize(document, {}), raw)
        current = parser.field_map(document)['gold'].value(document.payload)
        change = 999999 if current != 999999 else 999998
        edited = parser.decode(parser.serialize(document, {'gold': change}))
        allowed = set(range(parser.GOLD_OFFSET, parser.GOLD_OFFSET + 4))
        for offset in codec.CHECKSUM_OFFSETS:
            allowed.update(range(offset, offset + 4))
        self.assertTrue({i for i, (a, b) in enumerate(zip(document.payload, edited.payload)) if a != b} <= allowed)
        self.assertEqual(parser.field_map(edited)['gold'].value(edited.payload), change)
        self.assertEqual(edited.seed, document.seed)

    def test_native_weapon_and_stat_edits_remain_surgical(self):
        raw = Path(os.environ['SW4DX_SAVE_COPY']).read_bytes()
        document = parser.decode(raw)
        mapped = parser.field_map(document)
        candidates = [field for field in mapped.values() if field.id.endswith('_rank')
                      and field.minimum <= field.value(document.payload) < field.maximum]
        self.assertTrue(candidates, 'The supplied native copy has no upgradable mapped skill.')
        rank = candidates[0]
        attack = mapped['officer_0_attack']
        changes = {rank.id: rank.value(document.payload) + 1,
                   attack.id: min(attack.value(document.payload) + 1, attack.maximum)}
        edited = parser.decode(parser.serialize(document, changes))
        allowed = {rank.offset, rank.offset + 8, attack.offset, attack.offset + 1}
        for offset in codec.CHECKSUM_OFFSETS:
            allowed.update(range(offset, offset + 4))
        differences = {i for i, (a, b) in enumerate(zip(document.payload, edited.payload)) if a != b}
        self.assertTrue(differences <= allowed)
        self.assertEqual(rank.value(edited.payload), changes[rank.id])
        self.assertEqual(attack.value(edited.payload), changes[attack.id])
        self.assertEqual(edited.raw[:codec.PAYLOAD_OFFSET - 4], raw[:codec.PAYLOAD_OFFSET - 4])
