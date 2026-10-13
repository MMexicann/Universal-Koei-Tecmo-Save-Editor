"""Original Firis procedural and optional independently copied native checks."""
from dataclasses import replace
import os
from pathlib import Path
import struct
import tempfile
import unittest

from koei_editor.games.dw3.models import SaveError
from koei_editor.games.firis_pc import parser as p
from tests.scalar_contract import ScalarContractTests


def node(name, content):
    body = name.encode() + b'\0' + content
    return struct.pack('<I',len(body) + 4) + body


def fixture():
    raw = bytearray(b'\x97' * p.SAVE_SIZE)
    raw[:32] = p.HEADER
    roots = {}
    cursor = 32
    for name,size in p.ROOTS:
        head = struct.pack('<I',size) + name.encode() + b'\0'
        raw[cursor:cursor + len(head)] = head
        roots[name] = (cursor + len(head),cursor + size)
        cursor += size
    def put(root,content):
        a,b = roots[root]
        assert a + len(content) == b
        raw[a:b] = content
    put('money',node('money',struct.pack('>I',2043) + b'KEEP'))
    put('mix_lv',node('m_lv',struct.pack('>I',3)) + node('m_exp',struct.pack('>I',16)))
    party = node('version',b'\0\3') + struct.pack('>I',12)
    for i in range(12):
        party += node('Party',struct.pack('>I',i) + b'\x93' * (840 - 14))
    party += node('m_squad',struct.pack('>I',48) + b'\x91' * 48)
    party += node('m_battleMember',struct.pack('>I',16) + b'\x92' * 16)
    party += node('m_nLifePoint',struct.pack('>II',4,100))
    put('party',party)
    item = node('version',b'\0\3')
    for pool,_label,name,count,editable in p.POOLS:
        records = bytearray((b'\xff' * 4 + bytes(4) + b'\x98' * 44) * count)
        if editable:
            base = 100 if pool == 'basket' else 200
            for i,quality in enumerate((20.0,1200.0,12.5,float('nan'))):
                records[i * 52:i * 52 + 8] = struct.pack('>HHf',base + i,42 + i,quality)
        else:
            records[:8] = struct.pack('>HHf',300 + count + len(name),46,10)
        item += node(name,struct.pack('>I',len(records)) + records)
    item += node('limitSize',struct.pack('>II',60,1000)) + node('ID',b'\0\x7d\0\x7d')
    put('item',item)
    return bytes(raw)


class FirisFormatTests(unittest.TestCase):
    def setUp(self):
        self.raw = fixture()
        self.doc = p.decode(self.raw)

    def test_native_endianness_and_surgical_reductions(self):
        fields = p.field_map(self.doc)
        self.assertEqual(set(fields),{'cole','basket_1_quality','basket_2_quality',
                                     'container_1_quality','container_2_quality'})
        self.assertEqual(p.serialize(self.doc,{}),self.raw)
        for field in fields.values():
            edited = p.serialize(self.doc,{field.id:field.minimum})
            self.assertEqual(edited[:field.offset],self.raw[:field.offset])
            self.assertEqual(edited[field.offset + field.size:],self.raw[field.offset + field.size:])
            self.assertEqual(field.value(edited),field.minimum)
            self.assertEqual(p.stage(self.doc,{field.id:field.minimum},field.id,field.value(self.raw)),{})
        self.assertEqual(p.maximums(self.doc,{}),{})
        self.assertEqual(p.limit_values(self.doc,{},fields),{})

    def test_whole_number_quality_ownership_and_unusual_values(self):
        fields = p.field_map(self.doc)
        self.assertEqual(fields['basket_2_quality'].maximum,1200)
        for key,value in (('cole',2044),('basket_1_quality',21),('basket_1_quality',0),
                          ('basket_3_quality',1),('important_1_quality',1),
                          ('cole',True),('cole',1.0)):
            with self.subTest(key=key,value=value),self.assertRaises(SaveError):
                p.stage(self.doc,{},key,value)
        raw = bytearray(self.raw)
        basket = p._structure(self.raw)[0][0][2]
        container = p._structure(self.raw)[0][1][2]
        raw[container:container + 2] = raw[basket:basket + 2]
        ambiguous = p.field_map(p.decode(bytes(raw)))
        self.assertNotIn('basket_1_quality',ambiguous)
        self.assertNotIn('container_1_quality',ambiguous)
        self.assertEqual(p.serialize(p.decode(bytes(raw)),{}),bytes(raw))

    def test_active_inventory_limits_do_not_authorize_spare_physical_records(self):
        from koei_editor.games.firis_pc.editor import Presentation

        raw = bytearray(self.raw)
        pools = p._structure(self.raw)[0]
        for key, _label, base, _count, editable in pools:
            if not editable:
                continue
            # The first slot beyond each observed active limit retains a
            # plausible record but must not acquire a quality control.
            active = 60 if key == 'basket' else 1000
            struct.pack_into('>HHf', raw, base + active * 52, 900 + active, 42, 20)
        doc = p.decode(bytes(raw))
        self.assertNotIn('basket_61_quality', p.field_map(doc))
        self.assertNotIn('container_1001_quality', p.field_map(doc))
        self.assertEqual(p.serialize(doc, {}), bytes(raw))
        self.assertEqual(p.inventory_capacity_rows(doc),
                         (('Basket', 60, 100), ('Container', 1000, 4000)))
        tables = Presentation(p, p.GAME_ID).inspection_tables(doc)
        self.assertEqual(tables[1].rows, p.inventory_capacity_rows(doc))
        beyond = [row for row in tables[0].rows
                  if (row[0], row[1]) in (('Basket', 61), ('Container', 1001))]
        self.assertEqual(len(beyond), 2)
        self.assertTrue(all(row[-1] == 'Read only' for row in beyond))
        self.assertEqual(tables[0].rows[0][-1], 'Reduce only')

    def test_complete_foreign_and_forged_profile_rejection(self):
        for candidate in (self.raw[:-1],self.raw + b'\0',b'\0' * len(self.raw)):
            with self.assertRaises(SaveError):p.decode(candidate)
        for marker in (b'atelier_making\0',b'change_env_gimmick\0',b'm_unitContainer\0'):
            raw = bytearray(self.raw);raw[raw.index(marker)] ^= 1
            with self.assertRaises(SaveError):p.decode(bytes(raw))
        for key in ('raw','payload'):
            with self.assertRaises(SaveError):p.serialize(replace(self.doc,**{key:self.raw[:-1]}),{})
        with self.assertRaises(SaveError):p.decode(self.raw,'atelier_firis_dx')

    def test_changed_source_cannot_create_a_backup_or_save_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source';source.write_bytes(self.raw)
            doc = p.read_save(source)
            source.write_bytes(self.raw[:-1])
            with self.assertRaises(SaveError):p.backup(doc)
            with self.assertRaises(SaveError):p.save_as(doc,{},Path(folder) / 'edited')
            self.assertFalse((Path(folder) / 'WarriorsEditorBackups').exists())
            self.assertFalse((Path(folder) / 'edited').exists())

    @unittest.skipUnless(os.environ.get('FIRIS_PC_SAVE_COPY'),'No separate original Firis native copy')
    def test_optional_native_safe_copy_writer(self):
        raw = Path(os.environ['FIRIS_PC_SAVE_COPY']).read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'GAMEDATA-copy';source.write_bytes(raw)
            doc = p.read_save(source)
            self.assertEqual(p.serialize(doc,{}),raw)
            fields = p.field_map(doc)
            qualified = tuple(fields.values()) if isinstance(fields,dict) or hasattr(fields,'values') else fields
            pending = {f.id:f.minimum for f in qualified if f.value(doc.payload) != f.minimum}
            batch = p.decode(p.serialize(doc,pending))
            self.assertEqual(batch.payload,p.changed_payload(doc,pending))
            allowed = {i for f in qualified for i in range(f.offset,f.offset + f.size)}
            self.assertTrue(all(a == b or i in allowed for i,(a,b) in enumerate(zip(doc.payload,batch.payload))))
            for f in qualified:self.assertEqual(f.value(batch.payload),f.minimum)
            field = next(f for f in fields.values() if f.value(raw) > f.minimum)
            result = p.save_as(doc,{field.id:field.minimum},Path(folder) / 'edited-copy')
            self.assertEqual(source.read_bytes(),raw)
            self.assertEqual(field.value(result.payload),field.minimum)
            self.assertEqual(result.payload,p.changed_payload(doc,{field.id:field.minimum}))
            backup = p.backup(doc)
            p.restore(backup,Path(folder) / 'restored-copy')
            self.assertEqual((Path(folder) / 'restored-copy').read_bytes(),raw)


class FirisContractTests(ScalarContractTests,unittest.TestCase):
    game_id = p.GAME_ID

    def fixture_bytes(self):
        return fixture()
