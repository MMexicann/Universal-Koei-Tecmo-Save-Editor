"""3DS-specific structure and surgical tests; native fixture is private/optional."""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.hyrule_legends import parser as p


def procedural_legends():
    b=bytearray((i*7+43)&255 for i in range(p.SAVE_SIZE))
    b[:5]=p.LAYOUT_MARKER+b'\0';b[12:16]=p.SAVE_SIZE.to_bytes(4,'little');b[0xD3]=0xA0
    b[p.RUPEES_OFFSET:p.RUPEES_OFFSET+3]=(12345).to_bytes(3,'little')
    for offset,_ in p.MATERIALS:b[offset:offset+2]=bytes(2)
    b[p.MATERIALS[0][0]:p.MATERIALS[0][0]+2]=(12).to_bytes(2,'little')
    b[p.MATERIALS[1][0]:p.MATERIALS[1][0]+2]=(1001).to_bytes(2,'little')
    empty=bytes(16)+b'\xff\xff'+bytes(22)
    b[p.WEAPON_BASE:]=empty*p.WEAPON_COUNT
    o=p.WEAPON_BASE
    b[o+0x10:o+0x12]=(4).to_bytes(2,'little');b[o+0x12:o+0x14]=(280).to_bytes(2,'little')
    b[o+0x14:o+0x16]=(2).to_bytes(2,'little');b[o+0x16]=32;b[o+0x1E]=3;b[o:o+2]=(1000).to_bytes(2,'little')
    b[o+2:o+4]=(25000).to_bytes(2,'little');b[o+0x17]=41
    for offset,_ in p.MAP_CARDS: b[offset]=0
    b[p.MAP_CARDS[0][0]]=2
    b[p.MAP_CARDS[1][0]]=7
    for slot in range(p.FAIRY_COUNT): b[p.FAIRY_BASE + slot*p.FAIRY_STRIDE] = 0
    b[p.FAIRY_BASE] = 1
    o=p.FAIRY_BASE+p.FAIRY_NAME_DIFF
    b[o:o+p.FAIRY_NAME_SIZE]=b'Lumine\0x'
    return bytes(b)


class LegendsFormatTests(unittest.TestCase):
    def setUp(self):
        self.raw=procedural_legends();self.doc=p.decode(self.raw)

    def test_exact_unchanged_and_24bit_rupees_preserve_adjacent_byte(self):
        self.assertEqual(p.serialize(self.doc,{}),self.raw)
        out=p.serialize(self.doc,{'rupees':9_876_543})
        self.assertEqual(out[p.RUPEES_OFFSET:p.RUPEES_OFFSET+3],(9_876_543).to_bytes(3,'little'))
        self.assertEqual(out[:p.RUPEES_OFFSET],self.raw[:p.RUPEES_OFFSET])
        self.assertEqual(out[p.RUPEES_OFFSET+3:],self.raw[p.RUPEES_OFFSET+3:])
        self.assertEqual(p.FORMAT.fields[0].size,3)

    def test_foreign_revisions_shapes_and_exact_immutable_type(self):
        for raw in (self.raw[:-1],self.raw+b'\0',b'\0'*len(self.raw),self.raw[:4]+b'\1'+self.raw[5:],
                    self.raw[:12]+bytes(4)+self.raw[16:],self.raw[:0xD3]+b'\xa1'+self.raw[0xD4:]):
            with self.assertRaises(SaveError):p.decode(raw)
        with self.assertRaises(SaveError):p.decode(self.raw,'hyrule_definitive')
        for d in (replace(self.doc,raw=bytearray(self.raw)),replace(self.doc,payload=bytearray(self.raw)),
                  replace(self.doc,payload=self.raw[:-1]+bytes([self.raw[-1]^1]))):
            with self.assertRaises(SaveError):p.serialize(d,{})

    def test_owned_resources_max_exclusions_and_higher_originals(self):
        f=p.field_map(self.doc);self.assertIn('material_1924',f)
        self.assertIn('material_1926',f);self.assertNotIn('material_1928',f)
        self.assertEqual(p.maximums(self.doc,{}),{'weapon_1_stars':5})
        self.assertNotIn('weapon_1_skill_1_kos',p.maximums(self.doc,{}))
        raw=bytearray(self.raw);raw[p.WEAPON_BASE+0x14:p.WEAPON_BASE+0x16]=(8).to_bytes(2,'little')
        doc=p.decode(raw);self.assertEqual(p.maximums(doc,{}),{})
        self.assertEqual(p.stage(doc,{'weapon_1_stars':1},'weapon_1_stars',8),{})
        raw[p.RUPEES_OFFSET:p.RUPEES_OFFSET+3]=(12_000_000).to_bytes(3,'little');doc=p.decode(raw)
        self.assertEqual(p.stage(doc,{'rupees':1},'rupees',12_000_000),{})

    def test_surgical_weapon_stars_seals_and_foreign_future_ids(self):
        changes=p.stage(self.doc,{},'weapon_1_stars',5);changes=p.stage(self.doc,changes,'weapon_1_skill_1_kos',0)
        out=p.serialize(self.doc,changes);o=p.WEAPON_BASE
        self.assertLessEqual({i for i,(a,b) in enumerate(zip(self.raw,out)) if a!=b},{o,o+1,o+0x14,o+0x15})
        self.assertNotIn('weapon_1_skill_2_kos',p.field_map(self.doc))
        for identity,state in ((60,3),(4,11),(108,3),(109,3),(212,3),(4,0),(4,255)):
            raw=bytearray(self.raw);raw[o+0x10:o+0x12]=identity.to_bytes(2,'little');raw[o+0x1E]=state
            doc=p.decode(raw);self.assertNotIn('weapon_1_stars',p.field_map(doc));self.assertNotIn('weapon_1_skill_1_kos',p.field_map(doc))

    def test_invalid_edits_and_pending_validation_before_max(self):
        for edits in ({'rupees':True},{'rupees':10_000_000},{'rupees':-1},{'unmapped':1},
                      {'weapon_1_stars':6},{'weapon_1_skill_1_kos':1001}):
            with self.assertRaises(SaveError):p.serialize(self.doc,edits)
            with self.assertRaises(SaveError):p.maximums(self.doc,edits)
        with self.assertRaises(SaveError):p.stage(self.doc,{},'material_1924',0)

    def test_safe_copy_backup_restore_source_collision_and_suffix(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'zmha.bin';source.write_bytes(self.raw);doc=p.read_save(source)
            edited=source.with_name('edited.bin');p.save_as(doc,{'rupees':12},edited)
            self.assertEqual(source.read_bytes(),self.raw)
            snap=next((source.parent/'WarriorsEditorBackups').glob('*.bin'))
            restored=p.restore(snap,source.with_name('restored.bin'));self.assertEqual(restored.read_bytes(),self.raw)
            with self.assertRaises(FileExistsError):p.save_as(doc,{},edited)
            with self.assertRaises(SaveError):p.save_as(doc,{},source.with_name('wrong.dat'))
            source.write_bytes(self.raw[:-1]+bytes([self.raw[-1]^1]))
            with self.assertRaises(SaveError):p.save_as(doc,{},source.with_name('changed.bin'))

    def test_owned_fairy_name_surgical_padding_undo_and_invalid_values(self):
        key='fairy_1_name';field=p.field_map(self.doc)[key];o=field.offset
        self.assertEqual(field.kind,'text');self.assertEqual(field.value(self.raw),'Lumine')
        self.assertFalse(field.maxable)
        out=p.serialize(self.doc,p.stage(self.doc,{},key,'Navi'))
        self.assertEqual(out[o:o+8],b'Navi'+bytes(4))
        self.assertEqual(out[:o],self.raw[:o]);self.assertEqual(out[o+8:],self.raw[o+8:])
        self.assertEqual(p.stage(self.doc,{key:'Navi'},key,'Lumine'),{})
        self.assertEqual(p.serialize(self.doc,{key:'Lumine'}),self.raw)
        self.assertEqual(p.serialize(self.doc,{key:'ABCDEFGH'})[o:o+8],b'ABCDEFGH')
        for value in ('','123456789','Návi','A\0B','A\nB',True,1,b'Navi'):
            with self.assertRaises(SaveError):p.serialize(self.doc,{key:value})
            with self.assertRaises(SaveError):p.maximums(self.doc,{key:value})
        self.assertNotIn(key,p.maximums(self.doc,{},'My Fairy'))

    def test_fairy_ownership_unknown_names_and_all_other_record_bytes_preserved(self):
        o=p.FAIRY_BASE+p.FAIRY_NAME_DIFF
        for flag,name in ((0,b'Lumine\0x'),(2,b'Lumine\0x'),(255,b'Lumine\0x'),
                          (1,b'\xffLumine\0'),(1,bytes(8)),(1,b'A\nB'+bytes(5))):
            raw=bytearray(self.raw);raw[p.FAIRY_BASE]=flag;raw[o:o+8]=name
            doc=p.decode(raw);self.assertNotIn('fairy_1_name',p.field_map(doc))
            self.assertEqual(p.serialize(doc,{}),bytes(raw))
        self.assertNotIn('fairy_2_name',p.field_map(self.doc))

    def test_named_existing_map_cards_split_offsets_surgical_no_progress_or_max(self):
        field=p.field_map(self.doc)['map_card_2efa']
        self.assertEqual(field.label,'Adventure: Compass');self.assertFalse(field.maxable)
        out=p.serialize(self.doc,{'map_card_2efa':5})
        self.assertEqual(out[:0x2EFA],self.raw[:0x2EFA]);self.assertEqual(out[0x2EFB:],self.raw[0x2EFB:])
        self.assertIn('map_card_2efb',p.field_map(self.doc))
        self.assertNotIn('map_card_2efc',p.field_map(self.doc))
        self.assertEqual(p.maximums(self.doc,{},'Adventure map cards'),{})
        for value in (0,6,True,-1):
            with self.assertRaises(SaveError):p.serialize(self.doc,{'map_card_2efa':value})
        self.assertEqual(len(p.MAP_CARDS),60);self.assertEqual(len({o for o,_ in p.MAP_CARDS}),60)
        self.assertIn((0xEB56,'Great Sea: Compass'),p.MAP_CARDS)
        self.assertIn((0xEB5F,'Great Sea: Hookshot'),p.MAP_CARDS)
        self.assertIn((0xEB73,'Great Sea: Wind Waker'),p.MAP_CARDS)
        self.assertIn((0xA003,'Twilight: Water Bombs'),p.MAP_CARDS)
        self.assertIn((0xC5B1,'Termina: Ice Arrow'),p.MAP_CARDS)

    @unittest.skipUnless(os.environ.get('HYRULE_LEGENDS_COPY'),'Private native 3DS export absent')
    def test_native_roundtrip_every_qualified_field_and_master_preserved(self):
        source=Path(os.environ['HYRULE_LEGENDS_COPY']);raw=source.read_bytes();doc=p.decode(raw)
        self.assertEqual(p.serialize(doc,{}),raw);self.assertEqual(len(p.weapons(doc)),198)
        master=next(r for r in p.weapons(doc) if r['id']==60)
        for field in p.fields_for(doc):
            target=('Navi' if field.kind == 'text' else
                    max(field.minimum,min(field.maximum,field.value(raw)-1)))
            out=p.serialize(doc,p.stage(doc,{},field.id,target))
            self.assertLessEqual({i for i,(a,b) in enumerate(zip(raw,out)) if a!=b},set(range(field.offset,field.offset+field.size)))
            self.assertEqual(field.value(p.decode(out).payload),target)
            self.assertEqual(out[master['offset']:master['offset']+40],raw[master['offset']:master['offset']+40])
        self.assertEqual(source.read_bytes(),raw)
