"""Procedural versus optional private native Three Hopes exports."""
from dataclasses import replace
import os
from pathlib import Path
import struct
import tempfile
import unittest
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.three_hopes import parser as p
from koei_editor.games.three_hopes.editor import Editor
from tests.test_hyrule_gui import GuiWorkflow


def checksum_headers(raw):
    out=bytearray(raw);offset=p.BLOCK_START
    for index,size in enumerate(p.BLOCK_SIZES):
        end=p.NESTED_HEADER if index==2 else offset+size
        out[offset:offset+4]=sum(out[offset+16:end]).to_bytes(4,'little');offset+=size
    o=p.NESTED_HEADER;out[o:o+4]=sum(out[o+16:o+p.NESTED_SIZE]).to_bytes(4,'little')
    return bytes(out)


def procedural_hopes():
    b=bytearray(p.SAVE_SIZE);b[:4]=p.LAYOUT_MARKER;offset=p.BLOCK_START
    for size in p.BLOCK_SIZES:
        struct.pack_into('<4I',b,offset,0,size,1,0);offset+=size
    struct.pack_into('<4I',b,p.NESTED_HEADER,0,p.NESTED_SIZE,1,0)
    b[0x466734:]=bytes((i*19+31)&255 for i in range(p.SAVE_SIZE-0x466734))
    struct.pack_into('<I',b,p.GOLD_OFFSET,12345)
    for header,body,name in ((0x3C,0x841FC,b'Alice\0xy'),(0x64,0x84224,b'Byleth\0x')):
        b[header:header+8]=b[body:body+8]=name
    struct.pack_into('<H',b,p.DEPLOY_BASE,111);struct.pack_into('<I',b,p.RECRUIT_FLAGS,1)
    for index,identity in enumerate((110,111,0,1)):
        body=p.CHARACTER_BASE+index*p.CHARACTER_STRIDE+16
        struct.pack_into('<H',b,body+112,identity)
        struct.pack_into('<H',b,body+452,2500);struct.pack_into('<H',b,body+470,12)
    for index in range(p.WEAPON_COUNT):b[p.WEAPON_BASE+index*p.WEAPON_STRIDE+4]=255
    b[p.WEAPON_BASE+4]=6
    return checksum_headers(b)


class ThreeHopesTests(unittest.TestCase):
    def setUp(self):self.raw=procedural_hopes();self.doc=p.decode(self.raw)

    def test_complete_plaintext_noop_144_checksums_and_named_inspection(self):
        self.assertEqual(p.serialize(self.doc,{}),self.raw);self.assertEqual(len(p._objects(self.raw)),144)
        self.assertEqual(p.weapons(self.doc)[0]['name'],'Iron Sword')
        self.assertEqual(p.characters(self.doc)[0]['name'],'Shez (male)')
        self.assertEqual(set(p.field_map(self.doc)),{'gold','shez_name','byleth_name'})
        self.assertEqual(p.maximums(self.doc,{}),{})

    def test_surgical_gold_decrease_names_both_mirrors_and_one_own_checksum(self):
        for key,value in (('gold',2345),('shez_name','Navi'),('byleth_name','ABCDEFGH')):
            field=p.field_map(self.doc)[key];out=p.serialize(self.doc,{key:value})
            allowed=set(range(p.GAMEPLAY_HEADER,p.GAMEPLAY_HEADER+4))
            for at in (field.offset,)+field.mirrors:allowed.update(range(at,at+field.size))
            self.assertLessEqual({i for i,(a,b) in enumerate(zip(self.raw,out)) if a!=b},allowed)
            d=p.decode(out);self.assertEqual(p.field_map(d)[key].value(d.payload),value)
            self.assertEqual(out[0x466734:],self.raw[0x466734:])
        out=p.serialize(self.doc,{'shez_name':'Navi'})
        self.assertEqual(out[0x3C:0x44],b'Navi'+bytes(4));self.assertEqual(out[0x841FC:0x84204],b'Navi'+bytes(4))
        self.assertEqual(p.serialize(self.doc,{'shez_name':'Alice'}),self.raw)
        self.assertEqual(p.stage(self.doc,{'shez_name':'Navi'},'shez_name','Alice'),{})

    def test_original_ownership_and_positive_profiles_mirror_ascii_gates(self):
        cases=[(p.DEPLOY_BASE,b'\x80\x02','shez_name'),(p.RECRUIT_FLAGS,bytes(4),'byleth_name'),
               (0x3C,b'Other\0xx','shez_name'),(0x64,b'\xffyleth\0x','byleth_name'),
               (p.CHARACTER_BASE+p.CHARACTER_STRIDE+16+452,bytes(2),'shez_name'),
               (p.CHARACTER_BASE+2*p.CHARACTER_STRIDE+16+470,bytes(2),'byleth_name')]
        for at,value,key in cases:
            b=bytearray(self.raw);b[at:at+len(value)]=value;raw=checksum_headers(b);d=p.decode(raw)
            self.assertNotIn(key,p.field_map(d));self.assertEqual(p.serialize(d,{}),raw)
            with self.assertRaises(SaveError):p.serialize(d,{key:'Navi'})

    def test_all_sections_including_nested_child_reject_body_corruption(self):
        for _,begin,end in p._objects(self.raw):
            if end==begin:continue
            b=bytearray(self.raw);b[begin]^=1
            with self.assertRaises(SaveError):p.decode(b)
        b=bytearray(self.raw);b[p.NESTED_HEADER+16]=8
        # Parent integrity excludes child, while the child's integrity detects it.
        self.assertEqual(sum(b[0x964:p.NESTED_HEADER]),int.from_bytes(b[0x954:0x958],'little'))
        with self.assertRaises(SaveError):p.decode(b)

    def test_shape_revision_snapshot_and_forged_length_rejection(self):
        class SpoofBytes(bytes):
            def __len__(self):return p.SAVE_SIZE
        for b in (self.raw[:-1],self.raw+b'\0',SpoofBytes(self.raw+b'\0'),b'\0'*p.SAVE_SIZE):
            with self.assertRaises(SaveError):p.decode(b)
        b=bytearray(self.raw);b[p.GAMEPLAY_HEADER+8]=2
        with self.assertRaises(SaveError):p.decode(b)
        class EqualFormat:
            def __eq__(self,other):return True
        for d in (replace(self.doc,format=EqualFormat()),replace(self.doc,raw=bytearray(self.raw)),
                  replace(self.doc,payload=self.raw[:-1]+b'\0')):
            with self.assertRaises(SaveError):p.serialize(d,{})
        with self.assertRaises(SaveError):p.decode(self.raw,'fire_emblem_warriors')

    def test_invalid_values_pending_batch_and_malformed_container_atomic_rejection(self):
        for edits in ({'gold':12346},{'gold':True},{'gold':-1},{'recruit':1},{'shez_name':''},
                      {'shez_name':'ABCDEFGHI'},{'shez_name':'Návi'},{'shez_name':'A\0B'},
                      {'shez_name':'A\nB'},{'byleth_name':True},None,[],'gold'):
            with self.assertRaises(SaveError):p.serialize(self.doc,edits)
            with self.assertRaises(SaveError):p.maximums(self.doc,edits)
            with self.assertRaises(SaveError):p.stage(self.doc,edits,'gold',1)
        with self.assertRaises(SaveError):p.stage(self.doc,{},[],1)
        self.assertEqual(self.raw,self.doc.raw)

    def test_safe_extensionless_new_copy_backup_restore_and_source_change(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'SlotData3';source.write_bytes(self.raw);d=p.read_save(source)
            destination=source.with_name('SlotData-edited');p.save_as(d,{'shez_name':'Navi'},destination)
            self.assertEqual(source.read_bytes(),self.raw)
            snapshot=next(x for x in (source.parent/'WarriorsEditorBackups').iterdir() if x.suffix!='.json')
            restored=p.restore(snapshot,source.with_name('SlotData-restored'));self.assertEqual(restored.read_bytes(),self.raw)
            with self.assertRaises(FileExistsError):p.save_as(d,{},destination)
            with self.assertRaises(SaveError):p.save_as(d,{},source.with_name('bad.dat'))
            source.write_bytes(self.raw[:-1]+bytes([self.raw[-1]^1]))
            with self.assertRaises(SaveError):p.save_as(d,{},source.with_name('changed'))

    @unittest.skipUnless(os.environ.get('THREE_HOPES_COPY'),'Private Three Hopes native export absent')
    def test_private_native_every_exposed_field_surgical_and_original_untouched(self):
        path=Path(os.environ['THREE_HOPES_COPY']);raw=path.read_bytes();d=p.read_save(path)
        self.assertEqual(p.serialize(d,{}),raw);self.assertEqual(len(p._objects(raw)),144)
        for field in p.fields_for(d):
            target='Navi' if field.kind=='text' else max(0,field.value(raw)-1)
            out=p.serialize(d,{field.id:target});allowed=set(range(p.GAMEPLAY_HEADER,p.GAMEPLAY_HEADER+4))
            for at in (field.offset,)+field.mirrors:allowed.update(range(at,at+field.size))
            self.assertLessEqual({i for i,(a,b) in enumerate(zip(raw,out)) if a!=b},allowed)
            self.assertEqual(field.value(p.decode(out).payload),target)
        self.assertEqual(path.read_bytes(),raw)


class ThreeHopesGuiTests(GuiWorkflow,unittest.TestCase):
    backend=p;editor_type=Editor;fixture=staticmethod(procedural_hopes)
    group,search,field,value='Character names','Shez','shez_name','Navi'


@unittest.skipUnless(os.environ.get('THREE_HOPES_COPY'),'Private Three Hopes native export absent')
class ThreeHopesNativeGuiTests(GuiWorkflow,unittest.TestCase):
    backend=p;editor_type=Editor;fixture=staticmethod(lambda:Path(os.environ['THREE_HOPES_COPY']).read_bytes())
    group,search,field,value='Character names','Shez','shez_name','Navi'


def procedural_materials():
    raw = bytearray(procedural_hopes())
    # Independent literal geometry from the save template; distinctive record
    # tails expose accidental rewriting of opaque/discovery/reference bytes.
    for start, count in ((0x831BC, 8), (0x8366C, 4), (0x836BC, 3),
                         (0x836E4, 3), (0x8370C, 3), (0x83734, 3),
                         (0x8375C, 3), (0x83784, 3), (0x837AC, 3)):
        for slot in range(count):
            struct.pack_into('<H', raw, start + slot * 8, 20 + slot)
            raw[start + slot * 8 + 2:start + slot * 8 + 8] = bytes((137, 2, 231, 7, 61, 255))
    return checksum_headers(raw)


class ThreeHopesMaterialTests(unittest.TestCase):
    def setUp(self):
        self.raw = procedural_materials()
        self.doc = p.decode(self.raw)

    def test_each_of_33_stock_edits_preserves_opaque_record_tails_and_other_sections(self):
        fields = [field for field in p.fields_for(self.doc) if field.group == 'Material stocks']
        self.assertEqual(len(fields), 33)
        self.assertEqual(sum(row['group'] == 'Material stocks' for row in p.inspection_rows(self.doc)), 33)
        for field in fields:
            with self.subTest(field=field.id):
                out = p.serialize(self.doc, {field.id: 0})
                expected = bytearray(self.raw)
                expected[field.offset:field.offset + 2] = bytes(2)
                self.assertEqual(out, checksum_headers(expected))
                self.assertEqual(field.value(p.decode(out).payload), 0)
                self.assertNotIn(field.id, p.field_map(p.decode(out)))
                self.assertEqual(p.serialize(self.doc, {field.id: field.value(self.raw)}), self.raw)
        self.assertEqual(p.maximums(self.doc, {}), {})

    def test_original_stock_gate_and_all_pending_material_changes_are_validated(self):
        raw = bytearray(self.raw)
        raw[0x831BC:0x831BE] = bytes(2)
        raw[0x831C4:0x831C6] = b'\xff\xff'
        document = p.decode(checksum_headers(raw))
        for key in ('material_stones_1',):
            self.assertNotIn(key, p.field_map(document))
            with self.assertRaises(SaveError):
                p.stage(document, {}, key, 1)
        field = p.field_map(document)['material_stones_2']
        self.assertEqual(field.value(document.payload), 65535)
        self.assertEqual(p.stage(document, {}, field.id, 65535), {})
        self.assertEqual(p.serialize(document, {}), document.raw)
        key = 'material_training_1'
        for value in (21, -1, True, 3.0, '3'):
            for operation in (lambda: p.serialize(self.doc, {key: value}),
                              lambda: p.maximums(self.doc, {key: value}),
                              lambda: p.stage(self.doc, {key: value}, 'gold', 1)):
                with self.assertRaises(SaveError):
                    operation()
        pending = p.stage(self.doc, {}, key, 0)
        self.assertEqual(p.maximums(self.doc, pending), pending)
        self.assertEqual(p.stage(self.doc, pending, key, 20), {})


class ThreeHopesMaterialGuiTests(GuiWorkflow, unittest.TestCase):
    backend = p
    editor_type = Editor
    fixture = staticmethod(procedural_materials)
    group, search, field, value = 'Material stocks', 'Training gear', 'material_training_1', 3


@unittest.skipUnless(os.environ.get('THREE_HOPES_COPY'), 'Private Three Hopes native export absent')
class ThreeHopesNativeMaterialGuiTests(GuiWorkflow, unittest.TestCase):
    backend = p
    editor_type = Editor
    fixture = staticmethod(lambda: Path(os.environ['THREE_HOPES_COPY']).read_bytes())
    group, search, field, value = 'Material stocks', 'Training gear', 'material_training_1', 1
