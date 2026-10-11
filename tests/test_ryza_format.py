"""Procedural Ryza 2 native-profile and optional independent-file checks.

Generated buffers are deliberately non-playable; never count them as saves.
"""
from dataclasses import replace
from functools import lru_cache
import os
from pathlib import Path
import struct
import tempfile
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.ryza import codec, parser
from tests.scalar_contract import ScalarContractTests


def node(name, body):
    name = name.encode() + b'\0'
    return struct.pack('<I', 4 + len(name) + len(body)) + name + body


@lru_cache(maxsize=1)
def procedural_payload():
    stride = 100
    empty = bytearray((index * 19 + 7) & 255 for index in range(stride))
    struct.pack_into('<H', empty, 0, 0xFFFF)
    struct.pack_into('<h', empty, 4, -1)
    pools = []
    for key, tag, _label in parser.POOLS:
        capacity = {'basket': 200, 'important_basket': 150, 'container': 5000,
                    'important': 150, 'expendable': 50}[key]
        data = bytearray(bytes(empty) * capacity)
        if key in ('container', 'important', 'expendable'):
            struct.pack_into('<H', data, 0, {'container': 100, 'important': 101, 'expendable': 102}[key])
            struct.pack_into('<hHH', data, 4, 42, 75, 37)
        pools.append(node(tag.decode(), struct.pack('>I', len(data)) + data))
    party = []
    for identity in range(10):
        body = bytearray((index * 31 + identity + 11) & 255 for index in range(1290))
        struct.pack_into('>i', body, 0, identity if identity < 7 else -1)
        struct.pack_into('>I', body, 396, stride * 8)
        for slot in range(8):
            record = bytearray(empty)
            if identity < 7:
                struct.pack_into('<H', record, 0, identity * 8 + slot)
            if identity == 0 and slot == 0:
                struct.pack_into('<hHH', record, 4, 473, 30, 30)
            body[400 + slot * stride:400 + (slot + 1) * stride] = record
        party.append(node('Party', bytes(body)))
    return (bytes.fromhex('013379c9') + bytes(28)
            + node('info', node('app_ver', struct.pack('>II', 1, 1)))
            + node('fieldmap', node('_I_HOUSE_ABELHEIM', b'\1') + node('_T_CENTRAL', b'\2'))
            + node('item', node('version', b'\0\2') + b''.join(pools))
            + node('party', node('version', b'\0\3') + struct.pack('>I', 10) + b''.join(party)
                   + node('m_squad', struct.pack('>III', 0, 2, 4)))
            + node('AlchemyTree', node('ver', b'\0\2')) + node('ruin', b'\0')
            + node('Feeding', b'\0'))


def procedural_raw(payload=None):
    if payload is None:
        return _default_procedural_raw()
    return _encode_procedural_raw(payload)


@lru_cache(maxsize=1)
def _default_procedural_raw():
    # Only immutable fixture bytes are reused. Every test still decodes its
    # input and exercises the native integrity and gameplay validation paths.
    return _encode_procedural_raw(procedural_payload())


def _encode_procedural_raw(payload):
    header = bytearray((index * 23 + 5) & 255 for index in range(256))
    header[:48] = b'\1' + bytes(39) + struct.pack('<II', 1, 1)
    return codec.encode_file(bytes(header), payload, 0x12345678, b'\x13\x57\x9b')


class Ryza2Contract(ScalarContractTests, unittest.TestCase):
    game_id = 'atelier_ryza2'

    def fixture_bytes(self):
        return procedural_raw()


class Ryza2FormatTests(unittest.TestCase):
    def setUp(self):
        self.raw = procedural_raw()
        self.doc = parser.decode(self.raw, 'atelier_ryza2')

    def test_native_framing_and_foreign_profiles(self):
        for offset in (0, 40, 44, 256, len(self.raw) - 10):
            raw = bytearray(self.raw)
            raw[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(SaveError):
                parser.decode(raw, 'atelier_ryza2')
        for raw in (self.raw[:256], self.raw[:-16], b'\0' * 1024):
            with self.assertRaises(SaveError):
                parser.decode(raw, 'atelier_ryza2')
        for game_id in ('atelier_ryza', 'atelier_ryza3', 'atelier_sophie2', 'atelier_ryza2_dx'):
            with self.assertRaises(SaveError):
                parser.decode(self.raw, game_id)

    def test_all_edits_preserve_adjacent_values_and_native_envelope(self):
        fields = parser.fields_for(self.doc)
        self.assertEqual(len(fields), 3)
        for field in fields:
            with self.subTest(field=field.id):
                edited = parser.decode(parser.serialize(self.doc, {field.id: 100}), 'atelier_ryza2')
                touched = {index for index, pair in enumerate(zip(self.doc.payload, edited.payload))
                           if pair[0] != pair[1]}
                self.assertLessEqual(touched, {field.offset, field.offset + 1})
                self.assertEqual(edited.header, self.doc.header)
                self.assertEqual(edited.seed, self.doc.seed)
                self.assertEqual(edited.footer, self.doc.footer)
                self.assertEqual(edited.payload[field.offset + 2:field.offset + 4],
                                 self.doc.payload[field.offset + 2:field.offset + 4])
                self.assertFalse(field.maxable)
                with self.assertRaises(SaveError):
                    parser.stage(self.doc, {}, field.id, 101)
        self.assertEqual(parser.maximums(self.doc, {}), {})
        self.assertFalse(any('important' in field.id for field in fields))
        self.assertNotIn('character_0_1_quality', parser.field_map(self.doc))

    def test_structure_and_ownership_guards(self):
        b = self.doc.payload
        marker = b.find(b'm_unitContainer\0')
        body = marker + len(b'm_unitContainer\0')
        for offset, replacement in ((body, b'\0\0\0\1'), (body + 4, b'\xff\xff'),
                                    (body + 4 + 100, b'd\0')):
            payload = bytearray(b)
            payload[offset:offset + len(replacement)] = replacement
            if offset == body + 104:
                struct.pack_into('<h', payload, body + 108, 43)
            with self.assertRaises(SaveError):
                parser.decode(procedural_raw(bytes(payload)), 'atelier_ryza2')
        for bad in (b[:-1], b + node('item', b'\0'), b.replace(b'_T_CENTRAL', b'_T_INVALID')):
            with self.assertRaises(SaveError):
                parser.decode(procedural_raw(bad), 'atelier_ryza2')

    def test_unusual_originals_and_zero_quality(self):
        field = parser.fields_for(self.doc)[0]
        for value in (400, 1200):
            payload = bytearray(self.doc.payload)
            struct.pack_into('<H', payload, field.offset, value)
            doc = parser.decode(procedural_raw(bytes(payload)), 'atelier_ryza2')
            changes = parser.stage(doc, {}, field.id, 100)
            self.assertEqual(parser.stage(doc, changes, field.id, value), {})
            self.assertEqual(parser.serialize(doc, {field.id: value}), doc.raw)
            self.assertEqual(parser.maximums(doc, {}), {})
        payload = bytearray(self.doc.payload)
        struct.pack_into('<H', payload, field.offset, 0)
        doc = parser.decode(procedural_raw(bytes(payload)), 'atelier_ryza2')
        self.assertNotIn(field.id, parser.field_map(doc))

    @unittest.skipUnless(os.environ.get('RYZA2_SAVE_COPY'), 'No independent original Ryza 2 gameplay copy selected')
    def test_genuine_copy_roundtrip_surgical_save_backup_restore(self):
        source = Path(os.environ['RYZA2_SAVE_COPY'])
        with tempfile.TemporaryDirectory() as folder:
            copied = Path(folder) / 'native-reviewed-copy.dat'
            copied.write_bytes(source.read_bytes())
            doc = parser.read_save(copied, 'atelier_ryza2')
            self.assertEqual(parser.serialize(doc, {}), doc.raw)
            field = parser.fields_for(doc)[0]
            value = 100 if field.value(doc.payload) != 100 else 99
            changes = parser.stage(doc, {}, field.id, value)
            edited = parser.save_as(doc, changes, Path(folder) / 'edited.dat')
            self.assertEqual(edited.payload, parser.changed_payload(doc, changes))
            backup = parser.backup(doc)
            restored = parser.restore(backup, Path(folder) / 'restored.dat', 'atelier_ryza2')
            self.assertEqual(restored.read_bytes(), doc.raw)
            self.assertEqual(copied.read_bytes(), doc.raw)


if __name__ == '__main__':
    unittest.main()
