"""Native DW5 Special equipment tests; checked-in input is procedural."""
from dataclasses import replace
from functools import lru_cache
import os
from pathlib import Path
import tempfile
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.dw5special import dw5special_codec as codec
from koei_editor.games.dw5special import dw5special_parser as backend
from tests.scalar_contract import ScalarContractTests


def procedural_envelope(payload):
    result = bytearray(payload)
    result[codec.CHECKSUM_OFFSET:codec.CHECKSUM_OFFSET + 4] = sum(result[:codec.CHECKSUM_OFFSET]).to_bytes(4, 'little')
    return bytes(result)


@lru_cache(maxsize=1)
def procedural_raw():
    payload = bytearray((index * 31 + 17) & 255 for index in range(codec.SAVE_SIZE))
    payload[4:8] = codec.REVISION
    payload[backend.ITEM_BASE:backend.ITEM_BASE + 39] = bytes([255]) * 39
    payload[backend.ITEM_BASE] = 0
    payload[backend.ITEM_BASE + 9] = 19
    for identity in range(48):
        officer = backend.OFFICER_BASE + identity * 88
        payload[officer] = 1
        for weapon in range(4):
            start = officer + 20 + weapon * 16
            payload[start:start + 16] = bytes([228, 0, 1, 0, 39, 0, 39, 0, 39, 0, 39, 0, 39, 0, 0, 39])
    for identity, weapon in ((0, 0), (47, 3)):
        start = backend.OFFICER_BASE + identity * 88 + 20 + weapon * 16
        payload[start:start + 16] = bytes([identity * 4 + 3, 0, 1, 1, 0, 0, 2, 7, 9, 19, 39, 0, 39, 0, 40, 39])
    return procedural_envelope(payload)


class SpecialFormatTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.source = Path(self.folder.name) / 'special-copy.dat'
        self.source.write_bytes(procedural_raw())
        self.document = backend.read_save(self.source)

    def test_strict_profile_size_revision_checksum_and_frozen_input(self):
        raw = self.document.raw
        self.assertEqual(backend.serialize(self.document, {}), raw)
        for bad in (None, [], b'', raw[:-1], raw + b'\0', bytes(len(raw))):
            with self.subTest(kind=type(bad).__name__), self.assertRaises(SaveError):
                codec.decode(bad)
        for offset in (4, 200, codec.CHECKSUM_OFFSET):
            bad = bytearray(raw)
            bad[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(SaveError):
                backend.decode(bad)
        mutable = bytearray(raw)
        opened = backend.decode(mutable)
        mutable[100] ^= 1
        self.assertEqual(opened.raw, raw)

    def test_named_item_weapons_bounds_and_inspection_every_record(self):
        fields = backend.field_map(self.document)
        self.assertEqual(len(fields), 108)
        self.assertEqual(fields['item_0_rank'].offset, 0x1534)
        self.assertIn('Peacock', fields['item_0_rank'].label)
        self.assertIn('Zuo Ci', fields['officer_47_weapon_3_attribute_2'].label)
        self.assertEqual(fields['officer_47_weapon_3_attack'].offset, 0xEC + 47 * 88 + 20 + 3 * 16 + 14)
        self.assertEqual(backend.field_options(self.document, 'officer_0_weapon_0_weight'),
                         ((0, 'Light'), (1, 'Standard'), (2, 'Heavy')))
        self.assertEqual(backend.field_options(self.document, 'item_0_rank'), ())
        rows = backend.inspection_records(self.document)
        self.assertEqual(tuple(len(rows[key]) for key in ('officers', 'weapons', 'items', 'bodyguards')), (48, 192, 39, 8))

    def test_compatible_header_variant_preserves_mapping_and_surgical_writes(self):
        # Procedural regression for the exact marker found in an independently
        # checksum-valid native report; no player bytes are included here.
        payload = bytearray(self.document.raw)
        payload[4:8] = b'\x03\0\x01\0'
        document = backend.decode(procedural_envelope(payload))
        self.assertEqual(backend.serialize(document, {}), document.raw)
        self.assertEqual(backend.fields_for(document), backend.fields_for(self.document))
        self.assertEqual(backend.inspection_records(document),
                         backend.inspection_records(self.document))
        for field in backend.fields_for(document):
            value = (field.value(document.payload) + 1) % (field.maximum + 1)
            changes = backend.stage(document, {}, field.id, value)
            expected = bytearray(document.raw)
            expected[field.offset] = value
            actual = backend.serialize(document, changes)
            self.assertEqual(actual, procedural_envelope(expected))
            self.assertEqual(actual[4:8], document.raw[4:8])
            self.assertEqual(field.value(backend.decode(actual).payload), value)
            self.assertEqual(backend.stage(document, changes, field.id,
                                          field.value(document.payload)), {})

    def test_unqualified_header_variants_still_rejected_with_valid_checksum(self):
        for marker in (b'\x02\0\0\0', b'\x04\0\0\0', b'\x03\0\x02\0',
                       b'\x03\0\0\x01', b'\x03\x01\0\0'):
            payload = bytearray(self.document.raw)
            payload[4:8] = marker
            with self.subTest(marker=marker.hex()), self.assertRaises(SaveError):
                backend.decode(procedural_envelope(payload))

    def test_encoder_cannot_convert_between_supported_header_variants(self):
        for original_marker, edited_marker in ((b'\x03\0\0\0', b'\x03\0\x01\0'),
                                               (b'\x03\0\x01\0', b'\x03\0\0\0')):
            original = bytearray(self.document.raw)
            original[4:8] = original_marker
            original = procedural_envelope(original)
            payload = bytearray(original)
            payload[4:8] = edited_marker
            with self.subTest(original=original_marker.hex()), self.assertRaises(SaveError):
                codec.encode(procedural_envelope(payload), original)

    def test_each_field_surgical_only_selected_byte_and_checksum(self):
        raw = self.document.raw
        for field in backend.fields_for(self.document):
            value = (field.value(raw) + 1) % (field.maximum + 1)
            changed = backend.serialize(self.document, {field.id: value})
            self.assertEqual(field.value(backend.decode(changed).payload), value)
            expected = bytearray(raw)
            expected[field.offset] = value
            expected = procedural_envelope(expected)
            self.assertEqual(changed, expected)
            self.assertEqual(changed[codec.CHECKSUM_OFFSET + 4:], raw[codec.CHECKSUM_OFFSET + 4:])
        self.assertEqual(self.source.read_bytes(), raw)

    def test_empty_cross_family_unknown_identity_higher_rank_and_flags_preserved(self):
        start = 0x100
        for relative, value, excluded in ((0, 228, '_weight'), (0, 4, '_weight'),
                                          (1, 1, '_weight'), (2, 9, '_weight'),
                                          (5, 20, '_attribute_0'), (4, 39, '_attribute_0'),
                                          (14, 41, '_attack')):
            payload = bytearray(self.document.payload)
            payload[start + relative] = value
            doc = backend.decode(procedural_envelope(payload))
            key = 'officer_0_weapon_0' + excluded
            self.assertNotIn(key, backend.field_map(doc))
            with self.assertRaises(SaveError):
                backend.stage(doc, {}, key, 0)
            self.assertEqual(backend.serialize(doc, backend.maximums(doc, {})), doc.raw)
        for value in (20, 254, 255):
            payload = bytearray(self.document.payload)
            payload[backend.ITEM_BASE] = value
            doc = backend.decode(procedural_envelope(payload))
            self.assertNotIn('item_0_rank', backend.field_map(doc))
        for key in ('item_10_rank', 'officer_0_unlocked', 'officer_0_exp', 'officer_0_weapon_1_weight',
                    'bodyguard_0_skills', 'shura_gold'):
            with self.subTest(key=key), self.assertRaises(SaveError):
                backend.stage(self.document, {}, key, 1)

    def test_choices_ranks_manual_only_review_undo_and_invalid_values(self):
        for key, invalid in (('item_0_rank', 20), ('officer_0_weapon_0_weight', 3),
                             ('officer_0_weapon_0_attack', 41)):
            for value in (invalid, -1, True, 1.0, '1'):
                with self.subTest(key=key, value=value), self.assertRaises(SaveError):
                    backend.stage(self.document, {}, key, value)
        staged = backend.stage(self.document, {}, 'item_0_rank', 19)
        self.assertEqual(backend.maximums(self.document, staged), staged)
        self.assertEqual(backend.limit_values(self.document, staged, ['item_0_rank']), {})
        self.assertEqual(backend.stage(self.document, staged, 'item_0_rank', 0), {})
        self.assertEqual([(field.id, before, after) for field, before, after in backend.review(self.document, staged)],
                         [('item_0_rank', 0, 19)])
        self.assertTrue(all(not field.maxable for field in backend.fields_for(self.document)))

    def test_immutable_snapshot_original_and_payload_before_edit(self):
        class EqualFormat:
            def __eq__(self, other):
                return True

        doc = self.document
        for forged in (replace(doc, raw=bytearray(doc.raw)), replace(doc, payload=bytearray(doc.payload)),
                       replace(doc, payload=doc.payload[:-1] + bytes([doc.payload[-1] ^ 1])),
                       replace(doc, format=replace(doc.format, id='dw4hyper')), replace(doc, format=EqualFormat())):
            with self.assertRaises(SaveError):
                backend.serialize(forged, {})

    def test_malformed_pending_edits_reject_before_new_stage_or_undo(self):
        for pending in (None, [], [('item_0_rank', 2)], 'item_0_rank',
                        {'unknown': 1}, {'item_0_rank': True}, {'item_0_rank': 20}):
            for new_value in (0, 19):
                with self.subTest(pending=pending, value=new_value), self.assertRaises(SaveError):
                    backend.stage(self.document, pending, 'item_0_rank', new_value)
            with self.assertRaises(SaveError):
                backend.serialize(self.document, pending)

    def test_copy_backup_restore_and_changed_source(self):
        backup = backend.backup(self.document)
        destination = self.source.with_name('edited.dat')
        saved = backend.save_as(self.document, {'item_0_rank': 19}, destination)
        self.assertEqual(saved.source, destination.resolve())
        self.assertEqual(backend.field_map(saved)['item_0_rank'].value(saved.payload), 19)
        self.assertEqual(self.source.read_bytes(), self.document.raw)
        restored = backend.restore(backup, self.source.with_name('restored.dat'))
        self.assertEqual(restored.read_bytes(), self.document.raw)
        with self.assertRaises(FileExistsError):
            backend.save_as(self.document, {}, destination)
        self.source.write_bytes(self.document.raw[:-1] + bytes([self.document.raw[-1] ^ 1]))
        with self.assertRaises(SaveError):
            backend.save_as(self.document, {}, self.source.with_name('changed-source.dat'))

    @unittest.skipUnless(os.environ.get('DW5_SPECIAL_COPY'), 'Private genuine PC Special fixture not supplied')
    def test_genuine_premodified_save_roundtrip_every_field_surgical(self):
        source = Path(os.environ['DW5_SPECIAL_COPY'])
        raw = source.read_bytes()
        document = backend.decode(raw)
        self.assertEqual(backend.serialize(document, {}), raw)
        self.assertGreater(len(backend.fields_for(document)), 100)
        for field in backend.fields_for(document):
            value = (field.value(raw) + 1) % (field.maximum + 1)
            expected = bytearray(raw)
            expected[field.offset] = value
            actual = backend.serialize(document, {field.id: value})
            self.assertEqual(actual, procedural_envelope(expected))
            self.assertEqual(field.value(backend.decode(actual).payload), value)
        self.assertEqual(source.read_bytes(), raw)


class SpecialContract(ScalarContractTests, unittest.TestCase):
    game_id = 'dw5special'
    payload_integrity_offsets = frozenset(range(codec.CHECKSUM_OFFSET, codec.CHECKSUM_OFFSET + 4))

    def fixture_bytes(self):
        return procedural_raw()
