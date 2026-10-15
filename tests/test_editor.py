from pathlib import Path
import hashlib
import json
import struct
import sys
import tempfile
import shutil
import uuid
import unittest
from unittest.mock import patch

PROJECT=Path(__file__).resolve().parents[1]
WORKSPACE=PROJECT
sys.path.insert(0,str(PROJECT))
import koei_editor.games.dw3.save_writer as save_writer
from koei_editor.games.dw3.models import Change, SaveError, fields
from koei_editor.games.dw3.save_parser import read_save, parse_bytes, safe_path
from koei_editor.games.dw3.save_writer import CAPS, ITEM_CAPS, ITEMS, UNIQUE_WEAPONS, serialize, write_save, backup_save, restore_backup
from koei_editor.games.dw3.save_codec import CNG_AES, encrypt

FIXTURE=WORKSPACE/'work/original-upload/GameStatusData.sav'
RUNS=PROJECT/'tests/.test-runs'
RUNS.mkdir(parents=True,exist_ok=True)

class CodecTests(unittest.TestCase):
    def test_nist_aes256_ecb(self):
        key=bytes.fromhex('603deb1015ca71be2b73aef0857d77811f352c073b6108d72d9810a30914dff4')
        plain=bytes.fromhex('6bc1bee22e409f96e93d7e117393172a')
        expected=bytes.fromhex('f3eed1bdb5d2a03c064b5a7e3db181f8')
        with CNG_AES('ECB') as aes:
            self.assertEqual(aes.transform(plain,key,direction='encrypt'),expected)
            self.assertEqual(aes.transform(expected,key,direction='decrypt'),plain)

@unittest.skipUnless(FIXTURE.exists(),'The private uploaded fixture is required for integration tests.')
class SaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document=read_save(FIXTURE)
        cls.original_hash=hashlib.sha256(cls.document.encrypted).hexdigest()
    @classmethod
    def tearDownClass(cls):
        assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest()==cls.original_hash
    def setUp(self):
        self.folder=RUNS/('test-'+uuid.uuid4().hex)
        self.folder.mkdir()
    def tearDown(self):
        assert self.folder.resolve().is_relative_to(RUNS.resolve())
        shutil.rmtree(self.folder)
    def test_unchanged_roundtrip_is_identical(self):
        raw,audit=serialize(self.document)
        self.assertEqual(raw,self.document.encrypted)
        self.assertEqual(audit['plaintext_changes'],[])
        self.assertEqual(audit['changed_aes_blocks'],[])
    def test_first_officer_actual_values(self):
        record=fields(self.document.records('PCSaveDataArray')[0])
        self.assertEqual([record[n]['value'] for n in ('MaxHealth','MaxMusou','Attack','Defence','SPoint')],[190,210,132,135,99999])
    def test_one_merit_byte_changes_only_one_aes_block(self):
        raw,audit=serialize(self.document,[Change('officer',0,'SPoint',99998)])
        doc=parse_bytes(raw)
        offsets=[i for i,(a,b) in enumerate(zip(doc.plaintext,self.document.plaintext)) if a!=b]
        self.assertEqual(offsets,[2559]);self.assertEqual(audit['changed_aes_blocks'],[159])
        self.assertEqual(fields(doc.records('PCSaveDataArray')[0])['SPoint']['value'],99998)
    def test_legitimate_maxima_all42_and_story_preserved(self):
        changes=[Change('officer',i,n,v) for i in range(42) for n,v in CAPS.items()]
        raw,audit=serialize(self.document,changes);doc=parse_bytes(raw)
        for i in range(42):
            record=fields(doc.records('PCSaveDataArray')[i])
            for name,cap in CAPS.items():self.assertEqual(record[name]['value'],cap)
            original=fields(self.document.records('PCSaveDataArray')[i])
            for name in ('Progress','GeneralNameID','CanUseCostume'):
                self.assertEqual(record[name]['value'],original[name]['value'])
        for i in range(42,50):self.assertEqual(doc.records('PCSaveDataArray')[i],self.document.records('PCSaveDataArray')[i])
        for name in ('EngiClearCharaArray','ClearScenarioArray','CanUseCharaArray','EngiSaveDataArray'):
            self.assertEqual(doc.properties[name],self.document.properties[name])
    def test_stat_or_index_overflows_are_refused(self):
        for change in [Change('officer',0,'SPoint',100000),Change('officer',42,'SPoint',99999),
                       Change('officer',0,'Attack',151),Change('officer',0,'MaxHealth',0),
                       Change('officer',0,'Progress',7),Change('officer',0,'SPoint',True)]:
            with self.subTest(change=change):
                with self.assertRaises(SaveError):serialize(self.document,[change])
    def test_content_unlocks_leave_completion_and_placeholders(self):
        raw,_=serialize(self.document,[Change('unlock',i,'CanUseCharaArray',True) for i in range(42)])
        doc=parse_bytes(raw)
        self.assertEqual(doc.properties['CanUseCharaArray']['value']['values'][:42],[1]*42)
        self.assertEqual(doc.properties['CanUseCharaArray']['value']['values'][42:],self.document.properties['CanUseCharaArray']['value']['values'][42:])
        self.assertEqual(doc.properties['EngiClearCharaArray'],self.document.properties['EngiClearCharaArray'])
    def test_malformed_or_unsupported_rejected(self):
        for raw in (b'',self.document.encrypted[:-1],bytes(len(self.document.encrypted))):
            with self.assertRaises(SaveError):parse_bytes(raw)
        plain=bytearray(self.document.plaintext);struct.pack_into('<i',plain,16,1018)
        with self.assertRaises(SaveError):parse_bytes(encrypt(bytes(plain)))
    def test_backup_restore_and_corruption_refusal(self):
        backup=backup_save(self.document,self.folder/'backups')
        restored=restore_backup(backup,self.folder/'restored.sav')
        self.assertEqual(restored.read_bytes(),self.document.encrypted)
        backup.write_bytes(b'corrupted')
        with self.assertRaises(SaveError):restore_backup(backup,self.folder/'bad.sav')
        self.assertFalse((self.folder/'bad.sav').exists())
    def test_save_as_and_existing_destination_preserved(self):
        out=self.folder/'edited.sav';path,audit=write_save(self.document,out,[Change('officer',1,'SPoint',99999)])
        self.assertEqual(fields(read_save(path).records('PCSaveDataArray')[1])['SPoint']['value'],99999)
        original=out.read_bytes()
        with self.assertRaises(FileExistsError):write_save(self.document,out)
        self.assertEqual(out.read_bytes(),original)
        self.assertEqual(len(list(self.folder.glob('*.changes.json'))),1)
    def test_replacing_selected_copy_backs_up_old_bytes(self):
        source=self.folder/'copy.sav';source.write_bytes(self.document.encrypted)
        copy=read_save(source)
        write_save(copy,source,[Change('officer',0,'Attack',150)],overwrite=True)
        backup=next((self.folder/'DW3EditorBackups').glob('*.sav'))
        self.assertEqual(backup.read_bytes(),self.document.encrypted)
        self.assertEqual(fields(read_save(source).records('PCSaveDataArray')[0])['Attack']['value'],150)
    def test_item_unlock_resizes_only_its_tags_and_envelope(self):
        raw,audit=serialize(self.document,[Change('item',8,'Owned',True),Change('item',8,'Value',50)])
        doc=parse_bytes(raw);f=fields(doc.records('EquipItemDataArray')[8])
        self.assertEqual(f['EquipItemID']['value'],'EEquipItemID::EQUIP_ITEM_KYOUZOKUKAKU')
        self.assertEqual(f['Value']['value'],50);self.assertTrue(audit['resized'])
        for name in ('WeaponDataArray','UniqueWeaponDataArray','CollectedWeaponDataArray'):
            old=self.document.properties[name];new=doc.properties[name]
            self.assertEqual(self.document.plaintext[old['data_offset']:old['data_offset']+old['data_size']],doc.plaintext[new['data_offset']:new['data_offset']+new['data_size']])
        for name in ('ClearScenarioArray','EngiClearCharaArray'):
            self.assertEqual(doc.properties[name]['value'],self.document.properties[name]['value'])
    def test_all16_normal_caps_and27_rares(self):
        changes=[Change('item',i,'Owned',True) for i in ITEMS]
        changes.extend(Change('item',i,'Value',cap) for i,cap in ITEM_CAPS.items())
        raw,audit=serialize(self.document,changes);doc=parse_bytes(raw)
        self.assertEqual(len(ITEM_CAPS),16)
        for i,item in ITEMS.items():
            f=fields(doc.records('EquipItemDataArray')[i])
            self.assertEqual(f['EquipItemID']['value'],'EEquipItemID::'+item['enum'])
            self.assertEqual(f['Value']['value'],ITEM_CAPS.get(i,0))
        for i in range(43,100):
            self.assertEqual([p['value'] for p in doc.records('EquipItemDataArray')[i]],
                             [p['value'] for p in self.document.records('EquipItemDataArray')[i]])
    def test_bodyguard_merit_preserves_allocations_and_advances_count_ai(self):
        raw,_=serialize(self.document,[Change('bodyguard',i,'SPoint',99999) for i in range(4)])
        doc=parse_bytes(raw)
        for i in range(4):
            new=fields(doc.records('GuardDataArray')[i]);old=fields(self.document.records('GuardDataArray')[i])
            self.assertEqual(new['SPoint']['value'],99999)
            for name in new:
                if name not in ('SPoint','BGLevels'):self.assertEqual(new[name]['value'],old[name]['value'])
            for index in (0,1,2,4):
                self.assertEqual(new['BGLevels']['value']['values'][index],old['BGLevels']['value']['values'][index])
            self.assertEqual([new['BGLevels']['value']['values'][index] for index in (3,5)],[3,3])
    def test_unique_template_updates_inventory_and_collection(self):
        raw,_=serialize(self.document,[Change('unique_weapon',89,'Owned',True)])
        doc=parse_bytes(raw);template=UNIQUE_WEAPONS[89]
        for array,index,data_id in [('UniqueWeaponDataArray',0,10000),('CollectedWeaponDataArray',89,89)]:
            f=fields(doc.records(array)[index])
            self.assertEqual(f['WeaponID']['value'],template['weapon_enum'])
            self.assertEqual(f['ID']['value'],template['weapon_enum'])
            self.assertEqual(f['DataID']['value'],data_id)
            self.assertEqual(f['Attr']['value'],template['attribute_bitmask'])
            for slot,expected in zip(f['Skill']['value']['records'],template['skill_slots']):
                values=fields(slot)
                self.assertEqual(values['Value']['value'],expected['value'])
        again,audit=serialize(doc,[Change('unique_weapon',89,'Owned',True)])
        self.assertEqual(raw,again);self.assertEqual(audit['plaintext_changes'],[])
    def test_all84_supported_uniques_and_native_array_expansion(self):
        supported=list(UNIQUE_WEAPONS.values())
        self.assertEqual(len(supported),84)
        raw,_=serialize(self.document,[Change('unique_weapon',w['weapon_id'],'Owned',True) for w in supported])
        doc=parse_bytes(raw)
        self.assertEqual(len(doc.records('UniqueWeaponDataArray')),104)
        for w in supported:self.assertEqual(fields(doc.records('UniqueWeaponDataArray')[w['unique_save_index']])['WeaponID']['value'],w['weapon_enum'])
        for index in (41,42):
            def raw_record(document,index):
                records=document.records('UniqueWeaponDataArray')
                start=records[index][0]['tag_offset'];end=records[index+1][0]['tag_offset']
                return document.plaintext[start:end]
            self.assertEqual(raw_record(doc,index),raw_record(self.document,index))
        raw,_=serialize(self.document,[Change('unique_weapon',191,'Owned',True)])
        self.assertEqual(len(parse_bytes(raw).records('UniqueWeaponDataArray')),103)
    def test_stale_source_and_mutated_document_refused(self):
        source=self.folder/'copy.sav';source.write_bytes(self.document.encrypted);doc=read_save(source)
        source.write_bytes(b'new content')
        with self.assertRaises(SaveError):write_save(doc,source,overwrite=True)
        self.assertEqual(source.read_bytes(),b'new content')
        doc.plaintext=doc.plaintext[:-1]+b'\x01'
        with self.assertRaises(SaveError):serialize(doc)
    def test_item_placeholders_and_oversize_values_refused(self):
        for change in [Change('item',43,'Owned',True),Change('item',0,'Value',21),Change('item',13,'Value',1)]:
            with self.assertRaises(SaveError):serialize(self.document,[change])

    def test_debug_stages_and_bodyguard_merit_decreases_refused(self):
        for index in (108,149,150,155):
            with self.assertRaises(SaveError):
                serialize(self.document,[Change('unlock',index,'CanUseScenarioArray',True)])
        for i,record in enumerate(self.document.records('GuardDataArray')):
            merit=fields(record)['SPoint']['value']
            if merit:
                with self.assertRaises(SaveError):
                    serialize(self.document,[Change('bodyguard',i,'SPoint',0)])
        raw,_=serialize(self.document,[Change('unlock',i,'CanUseScenarioArray',True) for i in range(108)])
        edited=parse_bytes(raw)
        self.assertEqual(edited.properties['CanUseScenarioArray']['value']['values'][:108],[1]*108)
        self.assertEqual(edited.properties['CanUseScenarioArray']['value']['values'][108:],
                         self.document.properties['CanUseScenarioArray']['value']['values'][108:])
        self.assertEqual(edited.properties['ClearScenarioArray']['value'],self.document.properties['ClearScenarioArray']['value'])

    def test_invalid_weapon_field_sizes_and_unknown_enums_refused(self):
        f=fields(self.document.records('UniqueWeaponDataArray')[0])
        for field,bad_size in [('DataID',3),('Attr',4),('GetTime',4)]:
            plain=bytearray(self.document.plaintext)
            struct.pack_into('<i',plain,f[field]['size_offset'],bad_size)
            with self.subTest(field=field), self.assertRaises(SaveError):
                parse_bytes(encrypt(bytes(plain)))
        plain=bytearray(self.document.plaintext)
        plain[f['WeaponID']['data_offset']+4]=ord('X')
        with self.assertRaises(SaveError):parse_bytes(encrypt(bytes(plain)))

    def test_audit_failure_leaves_destination_untouched(self):
        source=self.folder/'copy.sav';source.write_bytes(self.document.encrypted)
        doc=read_save(source);real=save_writer._atomic_write
        def injected(data,path,overwrite=False,**kwargs):
            if str(path).endswith('.changes.json'):raise OSError('Simulated audit write failure')
            return real(data,path,overwrite,**kwargs)
        with patch.object(save_writer,'_atomic_write',side_effect=injected):
            with self.assertRaises(OSError):
                write_save(doc,source,[Change('officer',0,'Attack',150)],overwrite=True)
        self.assertEqual(source.read_bytes(),self.document.encrypted)
        self.assertFalse(list(self.folder.glob('*.changes.json')))

    def test_save_commit_failure_keeps_prepared_audit_and_unchanged_source(self):
        source=self.folder/'copy.sav';source.write_bytes(self.document.encrypted)
        doc=read_save(source)
        with patch.object(save_writer.os,'replace',side_effect=OSError('Simulated commit failure')):
            with self.assertRaises(OSError):
                write_save(doc,source,[Change('officer',0,'Attack',150)],overwrite=True)
        self.assertEqual(source.read_bytes(),self.document.encrypted)
        self.assertEqual(len(list(self.folder.glob('*.changes.json'))),1)
        self.assertFalse(list(self.folder.glob('.*.tmp')))

    def test_wrong_output_extension_refused(self):
        with self.assertRaises(SaveError):write_save(self.document,self.folder/'unrelated.txt')
        backup=backup_save(self.document,self.folder/'backups')
        with self.assertRaises(SaveError):restore_backup(backup,self.folder/'restored.txt')
        self.assertFalse((self.folder/'unrelated.txt').exists())
        self.assertFalse((self.folder/'restored.txt').exists())

class SafetyTests(unittest.TestCase):
    def test_live_paths_and_cloud_metadata_refused(self):
        for path in (r'C:\Users\Player\AppData\Local\KoeiTecmo\DW3CE_RE\Saved\SaveGames\GameStatusData.sav',
                     r'C:\a\steam_autocloud.vdf',r'C:\a\remotecache.vdf',
                     r'C:\Program Files (x86)\Steam\userdata\123\456\remote\GameStatusData.sav',
                     r'D:\userdata\123\456\remote\GameStatusData.sav'):
            with self.assertRaises(SaveError):safe_path(Path(path))

if __name__=='__main__':unittest.main()
