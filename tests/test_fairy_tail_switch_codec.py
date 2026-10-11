"""Native envelope proof, not gameplay editing or game-load validation."""
from dataclasses import replace
import os
from pathlib import Path
import struct
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.research.fairy_tail_switch import codec


def leaf(signature, body, revision):
    return struct.pack('<4sIIII', signature, 20, len(body), revision, codec.signed_fnv1a(body)) + body


def procedural_slot():
    chunks = []
    for index, (signature, revision, size) in enumerate(codec.BLOCK_LAYOUT):
        size = size if size is not None else 29
        body = bytes((position * 29 + index) % 256 for position in range(size))
        chunks.append(leaf(signature, body, revision))
    return leaf(b'#USR', b''.join(chunks), 0x10001)


class FairyTailEnvelopeTests(unittest.TestCase):
    def test_signed_char_checksum_known_answers(self):
        self.assertEqual(codec.signed_fnv1a(b''), 0x811C9DC5)
        self.assertEqual(codec.signed_fnv1a(bytes(4)), 0x4B95F515)
        self.assertEqual(codec.signed_fnv1a(b'\x80'), ((0x811C9DC5 ^ -128) * 0x1000193) & 0xFFFFFFFF)
        self.assertNotEqual(codec.signed_fnv1a(b'\xff'), ((0x811C9DC5 ^ 255) * 0x1000193) & 0xFFFFFFFF)

    def test_procedural_noop_and_frozen_snapshot(self):
        raw = procedural_slot()
        envelope = codec.decode(raw)
        self.assertIs(codec.encode(envelope), raw)
        self.assertIs(codec.checksum_patch(raw, b'#IND', envelope.blocks[4].body), raw)
        for forged in (replace(envelope, blocks=envelope.blocks[:-1]), replace(envelope, raw=bytearray(raw))):
            with self.assertRaises(SaveError):
                codec.encode(forged)

    def test_replacement_changes_only_selected_leaf_and_two_checksums(self):
        raw = procedural_slot()
        envelope = codec.decode(raw)
        block = envelope.blocks[4]
        body = bytearray(block.body)
        body[7] ^= 0x80
        result = codec.checksum_patch(raw, b'#IND', bytes(body))
        self.assertEqual(codec.decode(result).blocks[4].body, bytes(body))
        self.assertEqual(codec.decode(raw), envelope)
        allowed = {block.body_start + 7, *range(16,20), *range(block.start+16,block.start+20)}
        self.assertLessEqual({i for i,(a,b) in enumerate(zip(raw,result)) if a != b}, allowed)
        self.assertEqual(len(result), len(raw))

    def test_malformed_or_corrupt_blocks_reject(self):
        for position in (0,4,8,12,16,21,36,40,500):
            raw = bytearray(procedural_slot())
            raw[position] ^= 0x80
            with self.subTest(position=position), self.assertRaises(SaveError):
                codec.decode(bytes(raw))

    def test_valid_outer_checksum_does_not_hide_inner_corruption(self):
        raw = bytearray(procedural_slot())
        raw[41] ^= 0x80
        struct.pack_into('<I', raw, 16, codec.signed_fnv1a(bytes(raw[20:])))
        with self.assertRaisesRegex(SaveError, 'checksum'):
            codec.decode(bytes(raw))

    def test_unexpected_trailer_extent_type_and_signature_reject(self):
        raw = procedural_slot()
        envelope = codec.decode(raw)
        for body in (envelope.outer.body+b'\0', envelope.outer.body[:-1]):
            with self.assertRaises(SaveError):
                codec.decode(leaf(b'#USR',body,0x10001))
        for signature,body in ((b'#IND',b''),(b'#USR',envelope.outer.body),([],b''),(b'#IND',bytearray(b'x'))):
            with self.assertRaises(SaveError):
                codec.checksum_patch(raw,signature,body)
        for bad in (bytearray(raw), raw + b'\0', bytes(codec.MAX_SIZE + 1)):
            with self.assertRaises(SaveError):
                codec.decode(bad)

    def test_unknown_leaf_revision_rejects_with_valid_checksums(self):
        envelope = codec.decode(procedural_slot())
        altered = bytearray(envelope.outer.body)
        struct.pack_into('<I',altered,12,0x40002)
        with self.assertRaisesRegex(SaveError, 'revision'):
            codec.decode(leaf(b'#USR',bytes(altered),0x10001))

    def test_genuine_public_slots_noop_and_surgical_integrity(self):
        location = os.environ.get('FAIRY_TAIL_SWITCH_SAVE_COPIES')
        if not location:
            self.skipTest('Private native FAIRY TAIL Switch copies not supplied.')
        files = sorted(Path(location).glob('user_data_*'))
        self.assertGreaterEqual(len(files), 3)
        sizes = set()
        for path in files:
            raw = path.read_bytes()
            envelope = codec.decode(raw)
            sizes.add(len(raw))
            self.assertEqual(codec.encode(envelope),raw)
            self.assertTrue(all(codec.signed_fnv1a(block.body)==block.checksum for block in envelope.blocks))
            selected = envelope.blocks[4]
            opaque = bytearray(selected.body)
            opaque[0] ^= 1  # Codec-only opaque byte; never a gameplay claim.
            result = codec.checksum_patch(raw,b'#IND',bytes(opaque))
            self.assertEqual(codec.decode(result).blocks[4].body,bytes(opaque))
            allowed = {selected.body_start,*range(16,20),*range(selected.start+16,selected.start+20)}
            self.assertLessEqual({i for i,(a,b) in enumerate(zip(raw,result)) if a != b},allowed)
            self.assertEqual(path.read_bytes(),raw)
        self.assertGreaterEqual(len(sizes),3)

    def test_native_companion_checksums_independently_match_without_gameplay_writes(self):
        location = os.environ.get('FAIRY_TAIL_SWITCH_SAVE_COPIES')
        if not location:
            self.skipTest('Private native FAIRY TAIL Switch companions not supplied.')
        checked = 0
        for filename, outer_signature, signatures in (
                ('managed_data', b'#MNG', (b'#LSD',)),
                ('system_data', b'#SYS', (b'#STD', b'#SSD', b'#GRD'))):
            raw = (Path(location) / filename).read_bytes()
            outer = codec._block(raw, 0, len(raw))
            self.assertEqual(outer.signature, outer_signature)
            self.assertEqual(outer.end, len(raw))
            checked += 1
            position = 20
            for signature in signatures:
                block = codec._block(raw, position, outer.end)
                self.assertEqual(block.signature, signature)
                position = block.end
                checked += 1
            self.assertEqual(position, len(raw))
            with self.assertRaises(SaveError):
                codec.decode(raw)  # Companions are not gameplay slots.
        self.assertEqual(checked, 6)


if __name__ == '__main__':
    unittest.main()
