"""Synthetic diagnostic tests; not genuine-file or gameplay qualification."""
from dataclasses import FrozenInstanceError
import struct
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.research.sw2hd_ps3 import inspection


class SW2HDSourceCandidateTests(unittest.TestCase):
    @staticmethod
    def metadata(directory):
        key = b'SAVEDATA_DIRECTORY\0'
        value = directory.encode('ascii') + b'\0'
        return (struct.pack('<5I', 0x46535000, 0x101, 36, 36 + len(key), 1)
                + struct.pack('<HH3I', 0, 0x204, len(value), len(value), 0)
                + key + value)

    def test_matching_companion_never_qualifies_synthetic_gameplay(self):
        raw = bytes(inspection.MIN_CANDIDATE_SIZE)
        for directory in ('NPJB00439', 'NPJB00439-SAVEDATA'):
            result = inspection.inspect_export(raw, self.metadata(directory))
            self.assertEqual(result.candidate_title_id, 'NPJB00439')
            self.assertTrue(result.title_context_matches)
            self.assertTrue(result.payload_probe.checksums_match)
            self.assertFalse(result.editable)
            self.assertFalse(result.qualified_game_profile)
            self.assertFalse(hasattr(result, 'metadata'))
            self.assertFalse(hasattr(result, 'directory'))
            with self.assertRaises(FrozenInstanceError):
                result.editable = True

    def test_export_probe_rejects_empires_compilation_foreign_and_bad_metadata(self):
        raw = bytes(inspection.MIN_CANDIDATE_SIZE)
        for directory in ('NPJB00464-00', 'BLJM61092-SAVEDATA', 'NPJB004390',
                          'NPUB31564-SAVEDATA'):
            with self.assertRaises(SaveError):
                inspection.inspect_export(raw, self.metadata(directory))
        for metadata in (b'', b'\0' * 100, bytearray(self.metadata('NPJB00439')),
                         self.metadata('NPJB00439')[:-1]):
            with self.assertRaises(SaveError):
                inspection.inspect_export(raw, metadata)
        with self.assertRaises(SaveError):
            inspection.inspect_export(raw[:-1], self.metadata('NPJB00439'))

    def test_checksum_fact_big_endian_money_and_no_edit_support(self):
        raw = bytearray(inspection.MIN_CANDIDATE_SIZE + 20)
        raw[inspection.MONEY_OFFSET:inspection.MONEY_OFFSET + 4] = (123456).to_bytes(4, 'big')
        start, end = inspection.CHECKSUM_RANGE
        checksum = sum(raw[start:end])
        for offset in inspection.CHECKSUM_OFFSETS:
            raw[offset:offset + 4] = checksum.to_bytes(4, 'big')
        before = bytes(raw)
        result = inspection.inspect(before)
        self.assertEqual(result.candidate_money, 123456)
        self.assertEqual(result.expected_byte_sum, checksum)
        self.assertTrue(result.checksums_match)
        self.assertFalse(result.editable)
        self.assertFalse(result.qualified_game_profile)
        self.assertEqual(bytes(raw), before)
        raw[8] ^= 1
        self.assertFalse(inspection.inspect(bytes(raw)).checksums_match)
        for operation in ('stage', 'serialize', 'save_as', 'maximums'):
            self.assertFalse(hasattr(inspection, operation))

    def test_bounded_frozen_input_rejection(self):
        for raw in (b'', b'\0' * (inspection.MIN_CANDIDATE_SIZE - 1),
                    b'\0' * (inspection.MAX_CANDIDATE_SIZE + 1),
                    bytearray(inspection.MIN_CANDIDATE_SIZE)):
            with self.assertRaises(SaveError):
                inspection.inspect(raw)

    def test_published_record_anchors_are_raw_unqualified_immutable_probes(self):
        raw = bytearray(inspection.MIN_CANDIDATE_SIZE)
        for ordinal, (offset, _label) in enumerate(inspection.EXP_ANCHORS):
            raw[offset:offset + 4] = (0xFFFFFFFE - ordinal).to_bytes(4, 'big')
        for ordinal, (offset, _position) in enumerate(inspection.WEAPON_ANCHORS):
            raw[offset:offset + 0x13] = bytes(range(200 + ordinal, 219 + ordinal))
        before = bytes(raw)
        result = inspection.inspect(before)
        self.assertEqual([probe.stored_value for probe in result.experience_probes],
                         [0xFFFFFFFE, 0xFFFFFFFD, 0xFFFFFFFC])
        for probe, (offset, position) in zip(result.weapon_probes, inspection.WEAPON_ANCHORS):
            record = before[offset:offset + 0x13]
            self.assertEqual(probe.raw_record, record)
            self.assertEqual(probe.published_position, position)
            self.assertEqual(probe.stored_type, record[0])
            self.assertEqual(probe.stored_element, record[1])
            self.assertEqual(probe.stored_effect_ids, tuple(record[2:10]))
            self.assertEqual(probe.stored_effect_values, tuple(record[10:18]))
            self.assertEqual(probe.stored_effect_count, record[18])
            self.assertFalse(probe.ownership_qualified)
            with self.assertRaises(FrozenInstanceError):
                probe.stored_type = 0
        self.assertTrue(all(not probe.identity_qualified for probe in result.experience_probes))
        self.assertFalse(result.qualified_game_profile)
        self.assertEqual(bytes(raw), before)

    def test_partial_checksum_match_never_establishes_profile_or_full_integrity(self):
        raw = bytearray(inspection.MIN_CANDIDATE_SIZE)
        raw[8] = 17
        raw[9] = 23
        for offset in inspection.CHECKSUM_OFFSETS:
            raw[offset:offset + 4] = (40).to_bytes(4, 'big')
        self.assertTrue(inspection.inspect(bytes(raw)).checksums_match)
        # Header and later sections are outside the only published sum range.
        for offset in (0, 7, 0x36E4, 0x10000):
            changed = bytearray(raw)
            changed[offset] ^= 1
            result = inspection.inspect(bytes(changed))
            self.assertTrue(result.checksums_match)
            self.assertFalse(result.editable)
            self.assertFalse(result.qualified_game_profile)
        # Additive collisions inside the covered range are also possible.
        raw[8] -= 1
        raw[9] += 1
        self.assertTrue(inspection.inspect(bytes(raw)).checksums_match)
        # Each duplicate must independently match, including its endian encoding.
        for offset in inspection.CHECKSUM_OFFSETS:
            changed = bytearray(raw)
            changed[offset:offset + 4] = (40).to_bytes(4, 'little')
            self.assertFalse(inspection.inspect(bytes(changed)).checksums_match)
