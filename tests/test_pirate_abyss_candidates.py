"""Procedural checks and opt-in copied native outer-envelope roundtrips.

Neither the generators nor a no-edit native roundtrip prove game-load behavior.
"""
from dataclasses import replace
import os
from pathlib import Path
import struct
import unittest

import koei_editor.research.abyss.abyss_candidate_codec as abyss
import koei_editor.games.pw4.pw4_candidate_codec as pw4
from koei_editor.games.dw3.save_codec import CNG_AES


def pw4_procedural(size=0x2804, *, region='WW', seed=0x1234):
    payload = bytes((index * 37 + 19) & 255 for index in range(size - 4))
    output = bytearray()
    state = seed
    for word, in struct.iter_unpack('<I', payload):
        for _ in range(pw4.REGION_STEPS[region]):
            state = (0x5B1A7851 * state + 0xCE4E) % (2 ** 32)
        output.extend(struct.pack('<I', word ^ state))
    checksum = sum(word for word, in struct.iter_unpack('<H', payload)) & 0xFFFF
    return struct.pack('<HH', checksum, seed) + bytes(output), payload


def abyss_procedural(size=0x2800, *, owner=0, revision=0xA4):
    payload = bytearray((index * 53 + 71) & 255 for index in range(size - 32))
    struct.pack_into('<I', payload, 0, revision)
    # A procedural fake owner, not an account identifier or a native fixture.
    key = str(owner ^ 0xFABE9C015F6E379A).encode('ascii').ljust(32, b'\0')
    with CNG_AES('CBC') as provider:
        cipher = provider.transform(abyss.INNER_MAGIC + bytes(payload), key,
                                    direction='encrypt', iv=abyss.IV)
    return abyss.OUTER_MAGIC + cipher, bytes(payload)


class PW4CandidateTests(unittest.TestCase):
    def test_lcg_arithmetic_vectors(self):
        # Small arithmetic vectors, not binary/game execution or native saves.
        plain = bytes(range(12))
        for steps, expected in [(1, 'c2f1d45eb4ee97dcf6e98c54'),
                                (3, 'fee1845c2cee06cdbaf3dde5'),
                                (4, 'ac0ff39520f4bcfe94300bd8')]:
            cipher = pw4._cipher(plain, 0x1234, steps)
            self.assertEqual(cipher.hex(), expected)
            self.assertEqual(pw4._cipher(cipher, 0x1234, steps), plain)

    def test_explicit_region_roundtrip_unknown_bytes(self):
        for region in pw4.REGION_STEPS:
            with self.subTest(region=region):
                raw, payload = pw4_procedural(region=region)
                doc = pw4.decode_candidate(raw, region=region)
                self.assertEqual(doc.payload, payload)
                self.assertEqual(doc.unchanged_roundtrip(), raw)
                self.assertFalse(pw4.NATIVE_IDENTITY_VERIFIED)

    def test_large_observed_slot_size(self):
        raw, payload = pw4_procedural(0x27161C)
        doc = pw4.decode_candidate(raw, region='WW')
        self.assertEqual(doc.payload, payload)
        self.assertEqual(doc.unchanged_roundtrip(), raw)

    def test_wrong_region_and_corruption_rejected(self):
        raw, _ = pw4_procedural()
        for candidate, region in [(raw, 'AS'), (bytes([raw[0] ^ 1]) + raw[1:], 'WW'),
                                  (raw[:93] + bytes([raw[93] ^ 1]) + raw[94:], 'WW')]:
            with self.subTest(region=region):
                with self.assertRaises(ValueError):
                    pw4.decode_candidate(candidate, region=region)

    def test_invalid_sizes_types_and_regions(self):
        raw, _ = pw4_procedural()
        for candidate in [raw[:-1], raw + b'\0', raw[4:], len(raw), list(raw)]:
            with self.assertRaises(ValueError):
                pw4.decode_candidate(candidate, region='WW')
        for region in ['ww', '', None, 1, [], {}]:
            with self.assertRaises(ValueError):
                pw4.decode_candidate(raw, region=region)

    def test_freeze_input_and_reject_forged_snapshot(self):
        raw, payload = pw4_procedural()
        mutable = bytearray(raw)
        doc = pw4.decode_candidate(memoryview(mutable), region='WW')
        mutable[10] ^= 1
        self.assertEqual(doc.raw, raw)
        for forged in [replace(doc, payload=payload[:-1]),
                       replace(doc, payload=bytearray(payload)),
                       replace(doc, raw=bytearray(raw)), replace(doc, region='AS')]:
            with self.assertRaises(ValueError):
                forged.unchanged_roundtrip()

    @unittest.skipUnless(os.environ.get('PW4_SAVE_COPY') and os.environ.get('PW4_SAVE_REGION'),
                         'No copied native PW4 save and explicit region supplied.')
    def test_optional_native_copy_roundtrip(self):
        raw = Path(os.environ['PW4_SAVE_COPY']).read_bytes()
        doc = pw4.decode_candidate(raw, region=os.environ['PW4_SAVE_REGION'])
        self.assertEqual(doc.unchanged_roundtrip(), raw)


class AbyssCandidateTests(unittest.TestCase):
    def test_system_revision_is_bound_to_its_capacity(self):
        raw, payload = abyss_procedural(0x2800, revision=0x77)
        document = abyss.decode_candidate(raw, owner_context=0)
        self.assertEqual(document.payload, payload)
        self.assertEqual(document.unchanged_roundtrip(owner_context=0), raw)
        self.assertFalse(document.writable)
        for size, revision in [(0x30000, 0x77), (0x2800, 0x76), (0x30000, 0xA5)]:
            malformed, _ = abyss_procedural(size, revision=revision)
            with self.assertRaises(ValueError):
                abyss.decode_candidate(malformed, owner_context=0)

    def test_owner_key_derivation_without_account_retention(self):
        self.assertEqual(abyss._owner_key(0), b'18068050284766967706'.ljust(32, b'\0'))
        self.assertEqual(abyss._owner_key(abyss.OWNER_MASK), b'0'.ljust(32, b'\0'))
        for owner in [True, -1, 2 ** 64, '0', None, []]:
            with self.assertRaises(ValueError):
                abyss._owner_key(owner)

    def test_procedural_aligned_roundtrip_both_capacities(self):
        for size in abyss.OBSERVED_SIZES:
            with self.subTest(size=size):
                raw, payload = abyss_procedural(size)
                doc = abyss.decode_candidate(raw, owner_context=0)
                self.assertEqual(doc.payload, payload)
                self.assertEqual(doc.unchanged_roundtrip(owner_context=0), raw)
                self.assertFalse(doc.writable)
                self.assertFalse(doc.integrity_verified)
                self.assertEqual(set(vars(doc)), {'raw', 'payload'})

    def test_wrong_owner_magic_revision_and_sizes_rejected(self):
        raw, _ = abyss_procedural()
        with self.assertRaises(ValueError):
            abyss.decode_candidate(raw, owner_context=1)
        for malformed in [b'X' + raw[1:], raw[:-1], raw + b'\0', 10240, list(raw)]:
            with self.assertRaises(ValueError):
                abyss.decode_candidate(malformed, owner_context=0)
        # CBC alteration of the previous block flips the native revision byte.
        malformed = bytearray(raw)
        malformed[16] ^= 1
        with self.assertRaises(ValueError):
            abyss.decode_candidate(malformed, owner_context=0)

    def test_freeze_and_reject_forged_or_edited_snapshot(self):
        raw, payload = abyss_procedural()
        mutable = bytearray(raw)
        doc = abyss.decode_candidate(memoryview(mutable), owner_context=0)
        mutable[100] ^= 1
        self.assertEqual(doc.raw, raw)
        for forged in [replace(doc, payload=payload[:-1]),
                       replace(doc, payload=bytearray(payload)),
                       replace(doc, raw=bytearray(raw)),
                       replace(doc, payload=payload[:91] + b'X' + payload[92:])]:
            with self.assertRaises(ValueError):
                forged.unchanged_roundtrip(owner_context=0)

    def test_integrity_is_not_claimed_for_unknown_body_changes(self):
        raw, _ = abyss_procedural()
        malformed = bytearray(raw)
        malformed[1000] ^= 1
        doc = abyss.decode_candidate(malformed, owner_context=0)
        self.assertFalse(doc.integrity_verified)
        self.assertFalse(doc.writable)

    @unittest.skipUnless(os.environ.get('ABYSS_SAVE_COPY') and os.environ.get('ABYSS_SAVE_OWNER_CONTEXT'),
                         'No copied native Abyss save and original-owner context supplied.')
    def test_optional_native_copy_roundtrip(self):
        raw = Path(os.environ['ABYSS_SAVE_COPY']).read_bytes()
        owner = int(os.environ['ABYSS_SAVE_OWNER_CONTEXT'])
        doc = abyss.decode_candidate(raw, owner_context=owner)
        self.assertEqual(doc.unchanged_roundtrip(owner_context=owner), raw)

    @unittest.skipUnless(os.environ.get('ABYSS_NATIVE_COPY_DIRECTORY'),
                         'No private native Abyss slot/system copies and original VDF supplied.')
    def test_optional_native_sidecar_both_categories(self):
        from koei_editor.shared.steam_owner import read_owner
        directory = Path(os.environ['ABYSS_NATIVE_COPY_DIRECTORY'])
        for name, expected_revision in [('GAMEDATA00.BIN', 0xA4), ('SYSTEMDATA.BIN', 0x77)]:
            with self.subTest(category='game' if name.startswith('GAME') else 'system'):
                path = directory / name
                raw = path.read_bytes()
                context = read_owner(path)
                document = abyss.read_candidate_copy(path)
                self.assertEqual(struct.unpack_from('<I', document.payload)[0], expected_revision)
                self.assertEqual(document.unchanged_roundtrip(owner_context=context.steam_id64), raw)
                self.assertFalse(document.writable)
                self.assertFalse(document.integrity_verified)
                self.assertEqual(set(vars(document)), {'raw', 'payload'})
                with self.assertRaises(ValueError):
                    abyss.decode_candidate(raw, owner_context=context.account_id)
