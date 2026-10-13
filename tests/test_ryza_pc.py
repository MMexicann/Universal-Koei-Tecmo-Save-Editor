"""Original Ryza PC exact observed-profile tests; generated buffers are not saves."""
from functools import lru_cache
import os
from pathlib import Path
import struct
import tempfile
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.ryza_pc import parser as p
from tests.scalar_contract import ScalarContractTests
from tests.test_ryza_format import node


@lru_cache(maxsize=1)
def fixture_payload():
    raw = bytearray(b'\x97' * p.PAYLOAD_SIZE);raw[:32] = bytes.fromhex('013379c9') + bytes(28)
    roots = {};cursor = 32
    for name,size in p.ROOT_PROFILE:
        head = struct.pack('<I',size) + name.encode() + b'\0'
        raw[cursor:cursor + len(head)] = head;roots[name] = (cursor + len(head),cursor + size);cursor += size
    assert cursor == p.TAIL_START;raw[cursor:] = p.TAIL
    def put(name,content):
        a,b = roots[name];assert len(content) == b - a;raw[a:b] = content
    put('info',node('app_ver',struct.pack('>II',1,0)))
    a,_b = roots['fieldmap'];maps = node('_I_HOUSE_KLAUDIA_01',b'\1') + node('_T_BODEN',b'\2')
    raw[a:a + len(maps)] = maps
    empty = bytearray(b'\x93' * 66);struct.pack_into('<Hh',empty,0,65535,-1)
    item = node('version',b'\0\1')
    for key,tag,_label in p.POOLS:
        count = {'basket':200,'important_basket':100,'container':5000,'important':100,'expendable':50}[key]
        records = bytearray(bytes(empty) * count)
        if key in ('container','important','expendable'):
            struct.pack_into('<HhHH',records,0,{'container':100,'important':101,'expendable':102}[key],42,1200,0)
        item += node(tag.decode(),struct.pack('>I',len(records)) + records)
    item += node('limitSize',struct.pack('>II',125,5000)) + node('ID',b'\x09\x8a\x09\x89')
    item += node('Jewel',struct.pack('>II',4,100000))
    put('item',item)
    party = node('version',b'\0\3') + struct.pack('>I',9)
    for identity in range(9):
        body = bytearray(b'\x94' * 942);struct.pack_into('>i',body,0,identity if identity < 6 else -1)
        struct.pack_into('>I',body,396,8 * 66)
        for slot in range(8):
            record = bytearray(empty)
            if identity < 6:struct.pack_into('<H',record,0,identity * 8 + slot)
            if identity == 0 and slot == 0:struct.pack_into('<hHH',record,2,473,30,0)
            body[400 + slot * 66:400 + (slot + 1) * 66] = record
        party += node('Party',bytes(body))
    party += node('refs',b'\x92' * (roots['party'][1] - roots['party'][0] - len(party) - 9))
    put('party',party)
    return bytes(raw)


@lru_cache(maxsize=1)
def fixture():
    header = b'\1' + bytes(39) + struct.pack('<II',1,0) + b'\x8e' * 208
    return p.codec.encode_file(header,fixture_payload(),0x12345678,b'\x13\x57\x9b') + bytes(32)


class RyzaPcTests(unittest.TestCase):
    def setUp(self):
        self.doc = p.decode(fixture())

    def test_existing_quality_only_and_exact_native_tail_preservation(self):
        fields = p.field_map(self.doc)
        self.assertEqual(set(fields),{'container_0_quality','expendable_0_quality','character_0_0_quality'})
        self.assertEqual(fields['container_0_quality'].maximum,1200)
        self.assertEqual(p.serialize(self.doc,{}),self.doc.raw)
        for field in fields.values():
            reopened = p.decode(p.serialize(self.doc,{field.id:1}))
            self.assertEqual(reopened.payload[:field.offset],self.doc.payload[:field.offset])
            self.assertEqual(reopened.payload[field.offset + 2:],self.doc.payload[field.offset + 2:])
            self.assertEqual(reopened.payload[p.TAIL_START:],p.TAIL)
            self.assertEqual(len(reopened.payload),p.PAYLOAD_SIZE)
            for key in ('header','seed','footer','trailer'):
                self.assertEqual(getattr(reopened,key),getattr(self.doc,key))
            self.assertEqual(p.stage(self.doc,{field.id:1},field.id,field.value(self.doc.payload)),{})
        self.assertEqual(p.maximums(self.doc,{}),{})
        self.assertEqual(p.limit_values(self.doc,{},fields),{})

    def test_no_creation_increase_important_zero_or_coupled_quality(self):
        field = p.field_map(self.doc)['container_0_quality']
        for key,value in ((field.id,0),(field.id,1201),(field.id,True),(field.id,1.0),
                          ('important_0_quality',1),('money',1),('skill_points',1)):
            with self.subTest(key=key,value=value),self.assertRaises(SaveError):p.stage(self.doc,{},key,value)
        for value in (0,65535):
            data = bytearray(self.doc.payload);struct.pack_into('<H',data,field.offset,value)
            doc = p.decode(p.codec.encode_file(self.doc.header,bytes(data),self.doc.seed,self.doc.footer))
            self.assertNotIn(field.id,p.field_map(doc));self.assertEqual(p.serialize(doc,{}),doc.raw)
        data = bytearray(self.doc.payload);struct.pack_into('<H',data,field.offset + 2,37)
        doc = p.decode(p.codec.encode_file(self.doc.header,bytes(data),self.doc.seed,self.doc.footer))
        self.assertNotIn(field.id,p.field_map(doc));self.assertEqual(p.serialize(doc,{}),doc.raw)

    def test_integrity_complete_root_and_exact_opaque_profile_gates(self):
        damaged = bytearray(self.doc.raw);damaged[0x108] ^= 0x80
        with self.assertRaises(SaveError):p.decode(bytes(damaged))
        for data in (self.doc.payload[:-1],self.doc.payload + b'\0',
                     self.doc.payload.replace(b'FieldMix\0',b'OtherMix\0'),
                     self.doc.payload[:-1] + bytes([self.doc.payload[-1] ^ 1])):
            encoded = p.codec.encode_file(self.doc.header,data,self.doc.seed,self.doc.footer)
            with self.assertRaises(SaveError):p.decode(encoded)
        for game in ('atelier_ryza_switch','atelier_ryza2','atelier_ryza3_dx_pc',None,[],{}):
            with self.assertRaises(SaveError):p.decode(self.doc.raw,game)

    @unittest.skipUnless(os.environ.get('RYZA_PC_SAVE_COPY'),'No separate original Ryza PC reference copy')
    def test_optional_native_copy_writer(self):
        raw = Path(os.environ['RYZA_PC_SAVE_COPY']).read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'data.dat';source.write_bytes(raw)
            doc = p.read_save(source);self.assertEqual(p.serialize(doc,{}),raw)
            fields = p.fields_for(doc)
            qualified = tuple(fields.values()) if isinstance(fields,dict) or hasattr(fields,'values') else fields
            pending = {f.id:f.minimum for f in qualified if f.value(doc.payload) != f.minimum}
            batch = p.decode(p.serialize(doc,pending))
            self.assertEqual(batch.payload,p.changed_payload(doc,pending))
            allowed = {i for f in qualified for i in range(f.offset,f.offset + f.size)}
            self.assertTrue(all(a == b or i in allowed for i,(a,b) in enumerate(zip(doc.payload,batch.payload))))
            for f in qualified:self.assertEqual(f.value(batch.payload),f.minimum)
            field = next(f for f in p.fields_for(doc) if f.value(doc.payload) > 1)
            result = p.save_as(doc,{field.id:1},Path(folder) / 'edited.dat')
            self.assertEqual(source.read_bytes(),raw)
            self.assertEqual(result.payload,p.changed_payload(doc,{field.id:1}))
            self.assertEqual(result.payload[p.TAIL_START:],doc.payload[p.TAIL_START:])
            backup = p.backup(doc);p.restore(backup,Path(folder) / 'restored.dat')
            self.assertEqual((Path(folder) / 'restored.dat').read_bytes(),raw)


class RyzaPcContractTests(ScalarContractTests,unittest.TestCase):
    game_id = p.GAME_ID

    def fixture_bytes(self):
        return fixture()
