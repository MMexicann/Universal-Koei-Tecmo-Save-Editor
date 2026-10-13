"""Independent Three Hopes section-boundary and ownership review.

Checked-in bytes are procedural. THREE_HOPES_REVIEW_COPIES optionally supplies
six private native exports in the documented control order; none is published.
"""
from dataclasses import replace
from functools import lru_cache
import os
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.three_hopes import parser as p
from koei_editor.shared.verified_self_test import run as copied_save_test


def section_ranges(raw):
    """Traverse stored headers independently; handle the known nested child."""
    ranges = []
    at = 0x15C
    while at < 0x466734:
        _, size, _, _ = struct.unpack_from('<4I', raw, at)
        end = at + size
        ranges.append((at, at + 16, 0x6F3BC if at == 0x954 else end))
        at = end
    if at != 0x466734:
        raise AssertionError('Unexpected procedural/native section boundary')
    nested_size = struct.unpack_from('<I', raw, 0x6F3C0)[0]
    ranges.append((0x6F3BC, 0x6F3CC, 0x6F3BC + nested_size))
    return tuple(ranges)


def checksummed(data):
    result = bytearray(data)
    for header, start, end in section_ranges(result):
        total = 0
        for value in memoryview(result)[start:end]:
            total += value
        struct.pack_into('<I', result, header, total)
    return bytes(result)


@lru_cache(maxsize=1)
def procedural_copy():
    result = bytearray(0x50015C)
    result[:4] = bytes((1, 0, 0, 0))
    at = 0x15C
    sizes = [0x298, 0x560, 0x6EFC8, 0x85B0, 0x1DB20] + [0xD80] * 136 + [0x1AF0A4] * 2
    for size in sizes:
        struct.pack_into('<4I', result, at, 0, size, 1, 0)
        at += size
    struct.pack_into('<4I', result, 0x6F3BC, 0, 0x560, 1, 0)
    struct.pack_into('<I', result, 0x77F64, 12000)
    struct.pack_into('<I', result, 0x77FF4, 1)
    struct.pack_into('<H', result, 0x7864C, 111)
    for index, identity in enumerate((111, 0, 1)):
        body = 0x959FC + index * 0xD80
        struct.pack_into('<H', result, body + 112, identity)
        struct.pack_into('<H', result, body + 452, 2000)
        struct.pack_into('<H', result, body + 470, 10)
    for header, body, name in ((0x3C, 0x841FC, b'Leo\0xyzz'),
                              (0x64, 0x84224, b'Byleth\0x')):
        result[header:header + 8] = result[body:body + 8] = name
    result[0x466734:] = bytes((index * 23 + 7) & 255 for index in range(len(result) - 0x466734))
    return checksummed(result)


class IndependentThreeHopesAudit(unittest.TestCase):
    def setUp(self):
        self.raw = procedural_copy()
        self.document = p.decode(self.raw)

    def test_nested_child_is_excluded_from_parent_checksum_and_validated_separately(self):
        ranges = section_ranges(self.raw)
        self.assertEqual(len(ranges), 144)
        self.assertEqual(set(ranges), set(p._objects(self.raw)))
        modified = bytearray(self.raw)
        modified[0x6F3CC] = 17
        # Repairing the parent alone cannot make this corrupted child valid.
        parent_stored = struct.unpack_from('<I', modified, 0x954)[0]
        self.assertEqual(parent_stored, sum(modified[0x964:0x6F3BC]))
        with self.assertRaises(SaveError):
            p.decode(modified)
        modified[0x6F3BC:0x6F3C0] = (17).to_bytes(4, 'little')
        restored = p.decode(modified)
        self.assertEqual(restored.raw[0x954:0x958], self.raw[0x954:0x958])
        self.assertEqual(p.serialize(restored, {}), bytes(modified))

    def test_multiple_edits_change_only_own_checksum_names_and_gold(self):
        edits = {'shez_name': 'ABCDEFGH', 'byleth_name': 'Navi', 'gold': 11000}
        actual = p.serialize(self.document, edits)
        expected = bytearray(self.raw)
        for at in (0x3C, 0x841FC):
            expected[at:at + 8] = b'ABCDEFGH'
        for at in (0x64, 0x84224):
            expected[at:at + 8] = b'Navi'+bytes(4)
        struct.pack_into('<I', expected, 0x77F64, 11000)
        self.assertEqual(actual, checksummed(expected))
        for header, _, _ in section_ranges(self.raw):
            if header != 0x77ECC:
                self.assertEqual(actual[header:header + 16], self.raw[header:header + 16])
        self.assertEqual(actual[0x466734:], self.raw[0x466734:])
        self.assertEqual(p.serialize(self.document, {'shez_name': 'Leo'}), self.raw)
        self.assertEqual(p.maximums(self.document, edits), edits)

    def test_unknown_mirrors_ownership_and_nonascii_padding_are_readonly(self):
        cases = ((0x3C, b'Other\0xx', 'shez_name'),
                 (0x841FC, b'Leo\0\xffxyz', 'shez_name'),
                 (0x841FC, b'A\x7f'+bytes(6), 'shez_name'),
                 (0x7864C, (99).to_bytes(2, 'little'), 'shez_name'),
                 (0x959FC + 452, bytes(2), 'shez_name'),
                 (0x77FF4, bytes(4), 'byleth_name'),
                 (0x959FC + 0xD80 + 470, bytes(2), 'byleth_name'))
        for at, value, key in cases:
            with self.subTest(offset=at, key=key):
                data = bytearray(self.raw)
                data[at:at + len(value)] = value
                raw = checksummed(data)
                document = p.decode(raw)
                self.assertNotIn(key, p.field_map(document))
                self.assertEqual(p.serialize(document, {}), raw)
                with self.assertRaises(SaveError):
                    p.serialize(document, {key: 'Navi'})
        # The female recruit bit alone must not admit only a male profile.
        data = bytearray(self.raw)
        struct.pack_into('<I', data, 0x77FF4, 2)
        struct.pack_into('<H', data, 0x959FC + 2 * 0xD80 + 470, 0)
        self.assertNotIn('byleth_name', p.field_map(p.decode(checksummed(data))))

    def test_foreign_layout_headers_fail_even_with_valid_body_checksums(self):
        last_top_level = section_ranges(self.raw)[-2][0]
        for header in (0x15C, 0x954, 0x6F3BC, 0x77ECC, 0x959EC, last_top_level):
            for relative in (4, 8, 12):
                data = bytearray(self.raw)
                data[header + relative] ^= 1
                with self.subTest(header=header, relative=relative), self.assertRaises(SaveError):
                    p.decode(data)

    def test_max_preserves_unusual_balance_and_malformed_pending_is_atomic(self):
        data = bytearray(self.raw)
        struct.pack_into('<I', data, 0x77F64, 0xFFFFFFFF)
        document = p.decode(checksummed(data))
        self.assertEqual(p.serialize(document, p.maximums(document, {})), document.raw)
        self.assertEqual(p.serialize(document, {'gold': 0xFFFFFFFF}), document.raw)
        self.assertEqual(p.stage(document, {'gold': 1}, 'gold', 0xFFFFFFFF), {})
        pending = {'gold': 100, 'shez_name': 'Navi', 'byleth_name': 'TooLongName'}
        before = dict(pending)
        with self.assertRaises(SaveError):
            p.serialize(document, pending)
        self.assertEqual(pending, before)
        self.assertEqual(document.raw, checksummed(data))
        for changes in (None, [], True, {'gold': True}, {'unknown': 1}):
            for operation in (lambda: p.serialize(document, changes),
                              lambda: p.stage(document, changes, 'gold', 1),
                              lambda: p.maximums(document, changes)):
                with self.assertRaises(SaveError):
                    operation()
        for forged in (replace(document, raw=bytearray(document.raw)),
                       replace(document, payload=memoryview(document.payload)),
                       replace(document, format=replace(p.FORMAT))):
            with self.assertRaises(SaveError):
                p.serialize(forged, {})

    def test_registered_copied_save_report_uses_canonical_integrity(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'SlotData-copy'
            source.write_bytes(self.raw)
            report = copied_save_test('three_hopes', source, Path(folder) / 'review')
            self.assertEqual(report['integrity_kind'], 'checksum')
            self.assertTrue(report['success'])
            self.assertTrue(report['checksum_verified'])
            self.assertTrue(report['native_integrity_verified'])
            self.assertTrue(report['unchanged_roundtrip'])
            self.assertTrue(report['backup_restored'])
            self.assertEqual(report['fields_checked'], 3)
            self.assertEqual(report['fields_changed'], 0)
            self.assertFalse(report['in_game_load_tested'])
            self.assertEqual(source.read_bytes(), self.raw)

    @unittest.skipUnless(os.environ.get('THREE_HOPES_COPY'), 'No private admitted native SlotData3 export')
    def test_registered_native_cli_reports_qualified_fields_integrity_and_backup(self):
        source = Path(os.environ['THREE_HOPES_COPY'])
        original = source.read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'validation'
            result = subprocess.run(
                [sys.executable, '-m', 'koei_editor', '--game', 'three_hopes',
                 '--self-test', str(source), str(output)],
                cwd=folder, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((output / 'self-test-report.json').read_text())
            self.assertEqual(report['game_id'], 'three_hopes')
            self.assertEqual(report['fields_checked'], len(p.fields_for(p.read_save(source))))
            self.assertEqual(report['fields_changed'], 0)
            self.assertEqual(report['integrity_kind'], 'checksum')
            for key in ('success', 'checksum_verified', 'native_integrity_verified',
                        'unchanged_roundtrip', 'input_preserved', 'backup_restored'):
                self.assertTrue(report[key])
            self.assertFalse(report['in_game_load_tested'])
        self.assertEqual(source.read_bytes(), original)

    @unittest.skipUnless(os.environ.get('THREE_HOPES_REVIEW_COPIES'), 'No private native Three Hopes controls')
    def test_six_native_literal_checksums_unchanged_and_all_exposed_surgical_edits(self):
        paths = os.environ['THREE_HOPES_REVIEW_COPIES'].split(os.pathsep)
        expected = ((880065, 2871, 4216083), (797561, 3121, 4285187),
                    (797563, 3121, 4293470), (797563, 3121, 4269572),
                    (797154, 3121, 4216800),
                    (797161, 3121, 3691432))
        self.assertEqual(len(paths), len(expected))
        for index, (filename, control) in enumerate(zip(paths, expected)):
            with self.subTest(control=index):
                source = Path(filename)
                raw = source.read_bytes()
                self.assertEqual(tuple(struct.unpack_from('<I', raw, at)[0]
                                       for at in (0x954, 0x6F3BC, 0x77ECC)), control)
                self.assertEqual(raw, checksummed(raw))
                document = p.decode(raw)
                self.assertEqual(len(section_ranges(raw)), 144)
                self.assertEqual(p.serialize(document, {}), raw)
                for field in p.fields_for(document):
                    value = 'Navi' if field.kind == 'text' else max(0, field.value(raw) - 1)
                    actual = p.serialize(document, {field.id: value})
                    allowed = set(range(0x77ECC, 0x77ED0))
                    for at in (field.offset,) + field.mirrors:
                        allowed.update(range(at, at + field.size))
                    self.assertLessEqual({at for at, pair in enumerate(zip(raw, actual)) if pair[0] != pair[1]}, allowed)
                    self.assertEqual(actual, checksummed(actual))
                    self.assertEqual(field.value(p.decode(actual).payload), value)
                self.assertEqual(source.read_bytes(), raw)
