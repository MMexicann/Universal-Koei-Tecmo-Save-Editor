"""Read-only native comparisons, conditional fields, frozen reports and CLI."""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.shared import save_comparison as comparison
from koei_editor.games.dw3.models import SaveError
from koei_editor.games.deception4_ps3 import parser as deception
from koei_editor.games.dw6_ps3 import parser as dw6
from tests.test_ps3_new_families import fixture
from tests.test_ps3_expansion import PS3ContextTests
from tests.test_dw6_ps3 import fixture as dw6_fixture


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.folder=Path(temporary.name)
        self.first=self.folder/'first.bin';self.second=self.folder/'second.bin'
        self.first.write_bytes(fixture(deception));self.second.write_bytes(fixture(deception))
        self.metadata=self.folder/'PARAM.SFO'
        self.metadata.write_bytes(PS3ContextTests.metadata('NPUB31442-GAMEDATA-10'))

    def prepare(self):return comparison.prepare(deception.GAME_ID,self.first,self.second)

    def test_same_file_and_identical_copies_have_zero_differences_without_backups(self):
        for second in (self.first,self.second):
            result=comparison.prepare(deception.GAME_ID,self.first,second)
            self.assertEqual(result.rows,())
            self.assertEqual((result.unchanged_fields,result.changed_payload_bytes,result.outside_field_bytes),(1,0,0))
            self.assertTrue(comparison.report(result)['read_only'])
        self.assertFalse((self.folder/'UniversalEditorBackups').exists())

    def test_known_scalar_and_opaque_change_count_native_payload_bytes(self):
        raw=bytearray(deception.serialize(deception.decode(self.second.read_bytes()),{'warl':0x10203}))
        raw[-2]^=1;self.second.write_bytes(raw)
        result=self.prepare();self.assertEqual(result.outside_field_bytes,1)
        self.assertEqual(result.changed_payload_bytes,4)
        self.assertEqual(len(result.rows),1)
        row=result.rows[0]
        self.assertEqual((row.id,row.left,row.right,row.status),('warl',137,0x10203,'value_changed'))
        self.assertEqual(self.first.read_bytes(),fixture(deception))

    def test_higher_original_encoding_values_preserved_as_read_only_data(self):
        raw=bytearray(self.second.read_bytes());raw[0x20:0x24]=b'\xff'*4;self.second.write_bytes(raw)
        result=self.prepare();self.assertEqual(result.rows[0].right,0xFFFFFFFF)
        self.assertEqual(comparison.report(result)['differences'][0]['right'],0xFFFFFFFF)

    def test_conditional_availability_and_record_definitions_not_misreported_as_plain_values(self):
        raw=dw6_fixture();left=dw6.decode(raw);other=bytearray(raw)
        other[dw6.HORSE_BASE+4:dw6.HORSE_BASE+8]=(22).to_bytes(4,'big')
        base=dw6.OFFICER_BASE+8;other[base:base+4]=(4).to_bytes(4,'big')
        result=comparison.compare_documents(dw6.GAME_ID,left,dw6.decode(bytes(other)))
        rows={row.id:row for row in result.rows}
        self.assertEqual(rows['horse_0_speed'].status,'available_in_first')
        self.assertIsNone(rows['horse_0_speed'].right)
        self.assertEqual(rows['officer_0_weapon_0_damage_bonus'].status,'definition_changed')
        self.assertNotEqual(rows['officer_0_weapon_0_damage_bonus'].left_label,rows['officer_0_weapon_0_damage_bonus'].right_label)
        self.assertIn('Xiahou Dun',rows['officer_0_weapon_0_damage_bonus'].record)
        reverse=comparison.compare_documents(dw6.GAME_ID,dw6.decode(bytes(other)),left)
        self.assertEqual(next(row for row in reverse.rows if row.id=='horse_0_speed').status,'available_in_second')

    def test_wrong_game_foreign_mutable_and_damaged_input_never_fall_back(self):
        for game in ('dw3','atelier_escha_logy_dx','not-a-game'):
            with self.assertRaises(SaveError):comparison.prepare(game,self.first,self.second)
        result=self.prepare()
        for doc in (replace(result.left,raw=bytearray(result.left.raw)),replace(result.left,payload=b'')):
            with self.assertRaises(SaveError):comparison.compare_documents(deception.GAME_ID,doc,result.right)
        self.second.write_bytes(self.second.read_bytes()[:-1])
        with self.assertRaises(SaveError):self.prepare()
        with patch.object(deception,'read_save',side_effect=AssertionError('Wrong-extension input reached backend')):
            with self.assertRaises(SaveError):comparison.prepare(deception.GAME_ID,self.first.with_suffix('.dat'),self.second)

    def test_report_contains_values_and_hashes_without_paths_raw_or_owner_metadata(self):
        raw=deception.serialize(deception.decode(self.second.read_bytes()),{'warl':14});self.second.write_bytes(raw)
        result=self.prepare();output=self.folder/'report.json'
        self.assertEqual(comparison.export(result,output),output)
        report=json.loads(output.read_text());self.assertEqual(report['differences'][0]['right'],14)
        self.assertEqual(report['game_id'],deception.GAME_ID)
        self.assertEqual(report['first_sha256'],result.left.sha256)
        text=output.read_text()
        for private in (str(self.folder),'NPUB31442-GAMEDATA-10','context_digest','PARAM.SFO',self.first.name):
            self.assertNotIn(private,text)
        self.assertEqual(self.first.read_bytes(),fixture(deception))

    def test_forged_summary_rows_identity_and_wrong_report_extension_rejected(self):
        result=self.prepare()
        for forged in (replace(result,changed_payload_bytes=1),replace(result,unchanged_fields=7),
                       replace(result,game_id=dw6.GAME_ID),replace(result,rows=(None,)),
                       replace(result,unchanged_fields=True),replace(result,rows=[]) ):
            with self.assertRaises(SaveError):comparison.report(forged)
            with self.assertRaises(SaveError):comparison.export(forged,self.folder/'forged.json')
        with self.assertRaises(SaveError):comparison.export(result,self.folder/'report.bin')
        self.assertFalse((self.folder/'forged.json').exists())

    def test_existing_destination_source_change_and_original_context_change(self):
        result=self.prepare();output=self.folder/'report.json';output.write_text('existing')
        with self.assertRaises(FileExistsError):comparison.export(result,output)
        self.assertEqual(output.read_text(),'existing')
        for path in (self.first,self.metadata):
            original=path.read_bytes();path.write_bytes(original+b'changed')
            with self.assertRaises(SaveError):comparison.export(result,self.folder/'stale.json')
            self.assertFalse((self.folder/'stale.json').exists());path.write_bytes(original)

    def test_source_race_after_report_creation_invalidates_and_removes_only_new_report(self):
        result=self.prepare();output=self.folder/'report.json';original=comparison.atomic_new
        def changed(raw,destination):
            value=original(raw,destination);self.second.write_bytes(b'changed');return value
        with patch.object(comparison,'atomic_new',side_effect=changed),self.assertRaises(SaveError):
            comparison.export(result,output)
        self.assertFalse(output.exists());self.assertEqual(self.second.read_bytes(),b'changed')

    def test_headless_cli_json_export_and_argument_separation(self):
        output=self.folder/'cli.json'
        env=dict(os.environ,DISPLAY='')
        command=[sys.executable,'-m','koei_editor','--game',deception.GAME_ID,'--compare',str(self.first),str(self.second)]
        process=subprocess.run(command+['--comparison-report',str(output)],capture_output=True,text=True,env=env,timeout=30)
        self.assertEqual(process.returncode,0,process.stderr)
        self.assertEqual(json.loads(process.stdout),json.loads(output.read_text()))
        for args in (['--comparison-report',str(output)],['--compare',str(self.first),str(self.second)],
                     command[3:]+['--dry-run']):
            process=subprocess.run([sys.executable,'-m','koei_editor',*args],capture_output=True,text=True,env=env,timeout=30)
            self.assertNotEqual(process.returncode,0)
        self.assertEqual(self.first.read_bytes(),fixture(deception))

    def test_optional_independent_native_pair(self):
        first,second=os.environ.get('COMPARE_FIRST_COPY'),os.environ.get('COMPARE_SECOND_COPY')
        game_id=os.environ.get('COMPARE_GAME_ID')
        if not all((first,second,game_id)):self.skipTest('No private own-title native comparison pair selected')
        result=comparison.prepare(game_id,first,second)
        self.assertEqual(comparison.report(result)['different_fields'],len(result.rows))
        self.assertEqual(comparison.export(result,self.folder/'native.json').suffix,'.json')
