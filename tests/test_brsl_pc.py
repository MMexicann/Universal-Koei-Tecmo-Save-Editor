"""Source-backed Second Light native profile and shared-contract checks."""
from dataclasses import replace
import os
from pathlib import Path
import struct
import tempfile
import unittest

from koei_editor.games.blue_reflection_second_light_pc import parser as p
from koei_editor.games.dw3.models import SaveError
from tests.scalar_contract import ScalarContractTests


def node(name,content):
    body = name.encode() + b'\0' + content
    return struct.pack('<I',len(body) + 4) + body


def fixture_payload(profile=1):
    raw = bytearray(b'\x97' * p.PAYLOAD_SIZES[profile])
    raw[:32] = bytes.fromhex('013379c9') + bytes(28)
    cursor = 32;roots = {}
    for name,size in p.ROOT_PROFILES[profile]:
        head = struct.pack('<I',size) + name.encode() + b'\0'
        raw[cursor:cursor + len(head)] = head
        roots[name] = (cursor + len(head),cursor + size);cursor += size
    raw[cursor:] = p.TAIL
    def put(root,content):
        a,b = roots[root];assert len(content) == b - a;raw[a:b] = content
    put('info',node('app_ver',struct.pack('>II',1,profile)))
    item = node('version',struct.pack('>H',profile + 1))
    for label,name,count in p.POOLS:
        records = bytearray((b'\xff' * 4 + b'\x91' * 84) * count)
        if label == 'Container':
            records[:4] = struct.pack('<HH',7,42);records[6:8] = b'\x0b\0'
            records[88:92] = struct.pack('<HH',8,43);records[94:96] = b'\x01\0'
            records[176:180] = struct.pack('<HH',9,44);records[182:184] = b'\0\0'
            records[264:268] = struct.pack('<HH',10,45);records[270:272] = b'\x05\x01'
        else:
            records[:4] = struct.pack('<HH',100 + count,46);records[6:8] = b'\x0b\0'
        item += node(name,struct.pack('>I',len(records)) + records)
    item += node('limitSize',struct.pack('>I',5000)) + node('ID',b'\x07\x31\x07\x31')
    item += node('Jewel',struct.pack('>II',4,0))
    put('item',item)
    party = node('version',struct.pack('>H',profile + 5)) + struct.pack('>I',15)
    for index in range(15):
        party += node('Party',struct.pack('>I',index if index < 12 else 0xffffffff) + b'\x93' * (5374 - 14))
    party += node('refs',b'\x92' * (roots['party'][1] - roots['party'][0] - len(party) - 9))
    put('party',party)
    return bytes(raw)


def fixture(profile=1):
    header = struct.pack('<I',1) + bytes(36) + struct.pack('<II',1,profile) + b'\x8e' * 208
    return p.codec.encode_file(header,fixture_payload(profile),0x14567891,b'\x12\x34\x56') + bytes(32)


class BrslFormatTests(unittest.TestCase):
    def setUp(self):
        self.raw = fixture();self.doc = p.decode(self.raw)

    def test_positive_count_and_surgical_one_byte_reduction(self):
        fields = p.field_map(self.doc)
        self.assertEqual(set(fields),{'container_1_quantity'})
        field = fields['container_1_quantity']
        self.assertEqual(field.value(self.doc.payload),11)
        self.assertEqual(p.serialize(self.doc,{}),self.raw)
        raw = p.serialize(self.doc,{field.id:1});reopened = p.decode(raw)
        self.assertEqual(reopened.payload[:field.offset],self.doc.payload[:field.offset])
        self.assertEqual(reopened.payload[field.offset + 1:],self.doc.payload[field.offset + 1:])
        self.assertEqual(reopened.payload[-50:],p.TAIL)
        for key in ('header','seed','footer','trailer'):
            self.assertEqual(getattr(reopened,key),getattr(self.doc,key))
        self.assertEqual(p.stage(self.doc,{field.id:1},field.id,11),{})
        self.assertEqual(p.maximums(self.doc,{}),{})
        self.assertEqual(p.limit_values(self.doc,{},fields),{})

    def test_bounds_empty_unknown_and_ambiguous_records(self):
        for key,value in (('container_1_quantity',0),('container_1_quantity',12),
                          ('container_1_quantity',True),('container_1_quantity',1.0),
                          ('container_2_quantity',1),('container_3_quantity',1),
                          ('container_4_quantity',1),('money',1),('TP',1)):
            with self.subTest(key=key,value=value),self.assertRaises(SaveError):p.stage(self.doc,{},key,value)
        data = bytearray(self.doc.payload)
        regions = p._structure(self.doc.payload)[1]
        data[regions[1][1]:regions[1][1] + 2] = data[regions[0][1]:regions[0][1] + 2]
        duplicate = p.decode(p.codec.encode_file(self.doc.header,bytes(data),self.doc.seed,self.doc.footer))
        self.assertEqual(p.fields_for(duplicate),())
        self.assertEqual(p.serialize(duplicate,{}),duplicate.raw)

    def test_native_checksums_complete_geometry_and_tail_gates(self):
        for candidate in (self.raw[:-40],bytes(len(self.raw))):
            with self.assertRaises(SaveError):p.decode(candidate)
        damaged = bytearray(self.raw);damaged[0x100 + 8] ^= 0x80
        with self.assertRaises(SaveError):p.decode(bytes(damaged))
        for change in ('tail','root','party'):
            data = bytearray(self.doc.payload)
            offset = len(data) - 1 if change == 'tail' else data.index(b'SchoolDev\0')
            if change == 'party':offset = data.index(b'Party\0') + 6
            data[offset] ^= 1
            encoded = p.codec.encode_file(self.doc.header,bytes(data),self.doc.seed,self.doc.footer)
            with self.assertRaises(SaveError):p.decode(encoded)
        with self.assertRaises(SaveError):p.serialize(replace(self.doc,payload=self.doc.payload[:-1]),{})
        with self.assertRaises(SaveError):p.decode(self.raw,'blue_reflection_quartet')
        self.assertEqual(p.decode(fixture(0)).payload,fixture_payload(0))

    @unittest.skipUnless(os.environ.get('BRSL_PC_SAVE_COPY'),'No separately copied native Second Light save')
    def test_optional_native_safe_copy_writer(self):
        raw = Path(os.environ['BRSL_PC_SAVE_COPY']).read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'data.dat';source.write_bytes(raw)
            doc = p.read_save(source)
            self.assertEqual(p.serialize(doc,{}),raw)
            fields = p.fields_for(doc)
            qualified = tuple(fields.values()) if isinstance(fields,dict) or hasattr(fields,'values') else fields
            pending = {f.id:f.minimum for f in qualified if f.value(doc.payload) != f.minimum}
            batch = p.decode(p.serialize(doc,pending))
            self.assertEqual(batch.payload,p.changed_payload(doc,pending))
            allowed = {i for f in qualified for i in range(f.offset,f.offset + f.size)}
            self.assertTrue(all(a == b or i in allowed for i,(a,b) in enumerate(zip(doc.payload,batch.payload))))
            for f in qualified:self.assertEqual(f.value(batch.payload),f.minimum)
            self.assertTrue(fields,'Use a positive-count gameplay copy, not clear data')
            field = fields[0]
            result = p.save_as(doc,{field.id:1},Path(folder) / 'edited.dat')
            self.assertEqual(source.read_bytes(),raw)
            self.assertEqual(result.payload,p.changed_payload(doc,{field.id:1}))
            self.assertEqual(result.payload[-50:],doc.payload[-50:])
            backup = p.backup(doc)
            p.restore(backup,Path(folder) / 'restored.dat')
            self.assertEqual((Path(folder) / 'restored.dat').read_bytes(),raw)


class BrslContractTests(ScalarContractTests,unittest.TestCase):
    game_id = p.GAME_ID

    def fixture_bytes(self):
        return fixture()
