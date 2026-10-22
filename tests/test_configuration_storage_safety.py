"""Configuration writes require verified backups, owned staging and bound sources."""
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from koei_editor.shared import configuration_manager as config

GAME='arland_rorona_dx'
RAW=b'; original unknown comment\n[Window]\nFullScreen=0\n'

class WriteSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source=self.root/'ArlandDX_Settings.ini'; self.source.write_bytes(RAW)
        self.document=config.inspect_config(self.source,GAME)
        self.backups=self.root/'backups'

    def test_corrupted_backup_write_must_stop_save_before_original_changes(self):
        native_fsync=os.fsync
        calls=[]
        def corrupt_first_write(fd):
            calls.append(fd)
            if len(calls)==1:
                info=os.fstat(fd)
                os.lseek(fd,0,os.SEEK_SET); os.write(fd,b'X'*info.st_size)
            native_fsync(fd)
        with patch.object(config.os,'fsync',side_effect=corrupt_first_write):
            with self.assertRaises(config.ConfigurationError):
                config.save_config(self.document,{'fullscreen':1},self.backups)
        self.assertEqual(self.source.read_bytes(),RAW)

    def test_failed_record_write_must_preserve_foreign_replacement(self):
        uid='a'*32
        profile=self.root/'profiles'/f'{uid}.json'
        foreign=self.root/'foreign.json'; foreign.write_bytes(b'FOREIGN_RECORD_REPLACEMENT')
        native_fsync=os.fsync
        def replace_and_fail(fd):
            native_fsync(fd); foreign.replace(profile)
            raise OSError('synthetic write failure')
        with patch.object(config.uuid,'uuid4',return_value=SimpleNamespace(hex=uid)), \
             patch.object(config.os,'fsync',side_effect=replace_and_fail):
            with self.assertRaises(config.ConfigurationError):
                config.create_profile(self.document,'Windowed',profile.parent)
        self.assertTrue(profile.exists(),'Foreign replacement was deleted by record cleanup')
        self.assertEqual(profile.read_bytes(),b'FOREIGN_RECORD_REPLACEMENT')

    def stage_hooks(self,fail):
        native_temp=config.tempfile.NamedTemporaryFile
        native_fsync=os.fsync
        self.staging=[]
        foreign=self.root/'foreign-stage.bin'; foreign.write_bytes(b'FOREIGN_STAGING_CONTENT')
        def opened(*args,**kwargs):
            stream=native_temp(*args,**kwargs); self.staging.append(Path(stream.name)); return stream
        def sync(fd):
            native_fsync(fd)
            if self.staging and foreign.exists():
                foreign.replace(self.staging[-1])
                if fail: raise OSError('synthetic stage sync failure')
        return patch.object(config.tempfile,'NamedTemporaryFile',side_effect=opened), patch.object(config.os,'fsync',side_effect=sync)

    def test_staging_substitution_must_not_be_published_into_original(self):
        temp,sync=self.stage_hooks(False)
        with temp,sync:
            with self.assertRaises(config.ConfigurationError):
                config.save_config(self.document,{'fullscreen':1},self.backups)
        self.assertEqual(self.source.read_bytes(),RAW,'Unverified foreign staging replaced original before failure')

    def test_failed_stage_write_must_preserve_foreign_staging_replacement(self):
        temp,sync=self.stage_hooks(True)
        with temp,sync:
            with self.assertRaises(config.ConfigurationError):
                config.save_config(self.document,{'fullscreen':1},self.backups)
        self.assertEqual(self.source.read_bytes(),RAW)
        self.assertTrue(self.staging[-1].exists(),'Foreign staging replacement was deleted by failure cleanup')
        self.assertEqual(self.staging[-1].read_bytes(),b'FOREIGN_STAGING_CONTENT')

    def test_same_byte_source_replacement_requires_reinspection_before_any_backup(self):
        foreign=self.root/'replacement.ini'; foreign.write_bytes(RAW)
        foreign.replace(self.source)
        with self.assertRaises(config.ConfigurationChangedError):
            config.save_config(self.document,{'fullscreen':1},self.backups)
        with self.assertRaises(config.ConfigurationChangedError):
            config.create_backup(self.document,self.backups)
        self.assertEqual(self.source.read_bytes(),RAW)
        self.assertFalse(self.backups.exists())

    def test_relative_inspection_remains_bound_when_working_directory_changes(self):
        other=self.root/'other'; other.mkdir()
        second=other/self.source.name; second.write_bytes(RAW)
        previous=Path.cwd()
        try:
            os.chdir(self.root)
            document=config.inspect_config(self.source.name,GAME)
            self.assertEqual(document.path,self.source.resolve())
            os.chdir(other)
            saved=config.save_config(document,{'fullscreen':1},self.backups)
        finally:
            os.chdir(previous)
        self.assertEqual(saved.path,self.source.resolve())
        self.assertIn(b'FullScreen=1',self.source.read_bytes())
        self.assertEqual(second.read_bytes(),RAW)

    def test_parent_replacement_after_qualification_reads_no_outside_bytes(self):
        selected=self.root/'selected'; selected.mkdir()
        source=selected/self.source.name; source.write_bytes(RAW)
        outside=self.root/'outside'; outside.mkdir()
        (outside/self.source.name).write_bytes(RAW.replace(b'FullScreen=0',b'FullScreen=1'))
        probe=self.root/'link-probe'
        try:
            probe.symlink_to(outside,target_is_directory=True); probe.unlink()
        except (OSError,NotImplementedError):
            self.skipTest('Directory symlinks unavailable')
        native_safe=config.safe_path
        swapped=[]
        def swap_parent(path):
            resolved=native_safe(path)
            if Path(path)==source and not swapped:
                selected.rename(self.root/'held-selected')
                selected.symlink_to(outside,target_is_directory=True)
                swapped.append(True)
            return resolved
        with patch.object(config,'safe_path',side_effect=swap_parent), \
             patch.object(config.os,'read',side_effect=AssertionError('Outside bytes reached before qualification')) as read:
            with self.assertRaises(config.ConfigurationChangedError):
                config.inspect_config(source,GAME)
        self.assertEqual(swapped,[True])
        read.assert_not_called()

    def test_case_variant_filename_can_save_and_restore_using_canonical_backup_identity(self):
        path=self.root/'arlanddx_settings.ini'; path.write_bytes(RAW)
        document=config.inspect_config(path,GAME)
        saved=config.save_config(document,{'fullscreen':1},self.backups)
        backups=config.list_backups(self.backups,GAME)
        self.assertEqual(len(backups),1)
        record=(self.backups/(backups[0].id+'.json')).read_bytes()
        self.assertIn(config.FORMAT_FILENAME.encode(),record)
        restored=config.restore_backup(saved,backups[0].id,self.backups)
        self.assertEqual(restored.raw,RAW)
        self.assertEqual(restored.path,path.resolve())

if __name__=='__main__': unittest.main(verbosity=2)
