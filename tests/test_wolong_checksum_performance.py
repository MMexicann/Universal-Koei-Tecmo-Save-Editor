"""Optimized checksum equivalence against the original independent lane loop.

These are generated buffers, not player saves. No timing threshold controls
correctness: slow machines must still run exactly the same validation.
"""
import random
import struct
import unittest

from koei_editor.research.katana import katana_codec as codec


def reference_checksum(data):
    lanes = [0] * 7
    for index, value in enumerate(data):
        lanes[0] += value
        lanes[1 + ((index >> 2) & 1)] += value
        lanes[3 + (index & 3)] += value
    result = bytearray(32)
    struct.pack_into('<7H', result, 0, *(value & 0xffff for value in lanes))
    for index in range(31):
        result[index + 1] = (result[index + 1] + 2 * index + result[index]) & 255
    return bytes((codec._CHECKSUM_TABLE[32 + value] + codec._CHECKSUM_TABLE[index]) & 255
                 for index, value in enumerate(result))


class WolongChecksumEquivalenceTests(unittest.TestCase):
    def test_partial_block_boundaries_and_random_bytes(self):
        random_source = random.Random(0x23121200)
        lengths = (*range(65), 255, 256, 257, 1023, 1024, 1025, 65535, 65536, 65537)
        for length in lengths:
            data = random_source.randbytes(length)
            with self.subTest(length=length):
                self.assertEqual(codec._checksum(data), reference_checksum(data))

    def test_ushort_overflow_all_byte_values_and_native_body_size(self):
        for length in (256 * 1025, 5_120_272 - 0x100):
            data = (bytes(range(256)) * ((length + 255) // 256))[:length]
            with self.subTest(length=length):
                self.assertEqual(codec._checksum(data), reference_checksum(data))
        data = b'\xff' * 65537
        self.assertEqual(codec._checksum(data), reference_checksum(data))

    def test_mutable_bytes_have_the_same_checksum(self):
        data = bytes(range(256)) + b'partial'
        expected = reference_checksum(data)
        self.assertEqual(codec._checksum(bytearray(data)), expected)
        self.assertEqual(codec._checksum(memoryview(data)), expected)


if __name__ == '__main__':
    unittest.main()
