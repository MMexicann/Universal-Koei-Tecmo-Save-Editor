"""Regression cases from the complete v0.3 code review; copies only."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import struct
import sys
import unittest
import uuid
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
from koei_editor.games.dw3.models import Change, SaveError, fields
from koei_editor.games.dw3.save_parser import safe_path, read_save, parse_bytes
import koei_editor.games.dw3.save_writer as writer
import koei_editor.games.dw3.save_codec as save_codec
import koei_editor.games.dw3.unreal as unreal
import koei_editor.games.dw3.officer_weapon_editor as weapon
import koei_editor.games.dw3.bodyguard_editor as guard
from test_weapon_rolls import edited_fixture_bytes, enum_bytes

FIXTURE = PROJECT / 'work/original-upload/GameStatusData.sav'
RUNS = PROJECT / 'tests/.review-test-runs'


class PublicBoundaryTests(unittest.TestCase):
    def test_reader_rejects_invalid_bounds(self):
        for start, end in [(-1, 4), (0, 5), (3, 2)]:
            with self.subTest(start=start, end=end), self.assertRaises(unreal.FormatError):
                unreal.Reader(b'1234', start, end)

    def test_tag_payload_cannot_cross_its_parent_boundary(self):
        data = enum_bytes('Test') + enum_bytes('IntProperty') + struct.pack('<iiB', 0, 4, 0)
        data += b'1234' + enum_bytes('None')
        with self.assertRaises(unreal.FormatError):
            unreal.tags(unreal.Reader(data, 0, len(data) - 8))

    def test_short_plaintext_returns_validation_error(self):
        for data in (b'', b'1', b'123'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                save_codec.encrypt(data)
            with self.subTest(data=data), self.assertRaises(unreal.FormatError):
                unreal.parse(data)

    def test_resolved_cloud_metadata_name_is_blocked(self):
        for name in ('steam_autocloud.vdf', 'remotecache.vdf'):
            with patch.object(Path, 'resolve', return_value=Path('C:/review/' + name)):
                with self.assertRaises(SaveError):
                    safe_path(Path('C:/review/alias.sav'))

    def test_exact_protected_directory_paths_are_blocked(self):
        for path in ('C:/review/KoeiTecmo/DW3CE_RE/Saved', 'C:/review/Steam/userdata'):
            with self.assertRaises(SaveError):
                safe_path(Path(path))

    @unittest.skipUnless(os.name == 'nt', 'Windows file name rules.')
    def test_windows_stream_and_device_names_are_blocked(self):
        for name in ('copy.sav:other.sav', 'CON.sav', 'NUL.sav', 'COM1.sav'):
            with self.subTest(name=name), self.assertRaises(SaveError):
                safe_path(PROJECT / 'tests' / name)


class CopyTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = read_save(FIXTURE)
        cls.fixture_hash = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        RUNS.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == cls.fixture_hash

    def setUp(self):
        self.folder = RUNS / uuid.uuid4().hex
        self.folder.mkdir()

    def tearDown(self):
        assert self.folder.resolve().is_relative_to(RUNS.resolve())
        shutil.rmtree(self.folder)


@unittest.skipUnless(FIXTURE.exists(), 'The explicitly supplied private fixture is required.')
class ReviewIntegrationTests(CopyTestCase):
    def test_unfamiliar_saved_items_are_preserved_and_new_edits_validated(self):
        normal = fields(self.document.records('EquipItemDataArray')[0])
        rare_id = next(i for i, row in writer.ITEMS.items() if row['kind'] == 'rare')
        rare = fields(self.document.records('EquipItemDataArray')[rare_id])
        cases = [
            [(normal['EquipItemID'], enum_bytes('EEquipItemID::' + writer.ITEMS[1]['enum']))],
            [(normal['Value'], struct.pack('<i', -1))],
            [(normal['Value'], struct.pack('<i', writer.ITEM_CAPS[0] + 1))],
            [(normal['EquipItemID'], enum_bytes('EEquipItemID::NUM')), (normal['Value'], struct.pack('<i', 1))],
            [(normal['GuardEquipItemID'], enum_bytes(guard.GUARD_ITEMS[0]['enum']))],
            [(rare['EquipItemID'], enum_bytes('EEquipItemID::' + writer.ITEMS[rare_id]['enum'])), (rare['Value'], struct.pack('<i', 1))],
        ]
        for index, replacements in enumerate(cases):
            with self.subTest(case=index):
                raw=edited_fixture_bytes(self.document,replacements)
                document=parse_bytes(raw)
                self.assertTrue(document.compatibility_warnings)
                self.assertEqual(writer.serialize(document)[0],raw)
                if index in (0,4):
                    with self.assertRaises(SaveError):writer.serialize(document,[Change('item',0,'Value',1)])
                elif index==5:
                    self.assertEqual(writer.serialize(document,[Change('item',rare_id,'Owned',True)])[0],raw)
                elif index==1:
                    with self.assertRaises(SaveError):writer.serialize(document,[Change('item',0,'Value',-1)])
                elif index==2:
                    self.assertEqual(writer.serialize(document,[Change('item',0,'Value',writer.ITEM_CAPS[0]+1)])[0],raw)
                    with self.assertRaises(SaveError):writer.serialize(document,[Change('item',0,'Value',writer.ITEM_CAPS[0]+2)])

    def test_unknown_native_bonus_is_view_only_and_roundtrips(self):
        row = fields(self.document.records('WeaponDataArray')[36])
        slot = fields(row['Skill']['value']['records'][0])
        raw = edited_fixture_bytes(self.document, [(slot['EquipItemID'], enum_bytes('EEquipItemID::EquipItemID_043'))])
        document = parse_bytes(raw)
        info = weapon.state(document, 36)
        self.assertFalse(info['editable'])
        self.assertEqual(info['skills'][0]['id'], 43)
        self.assertEqual(writer.serialize(document)[0], raw)
        with self.assertRaises(SaveError):
            writer.serialize(document, [Change('weapon_roll', 36, 'Skills', info['skills'])])

    def test_redundant_acquisition_cannot_bypass_owned_reference_check(self):
        template = writer.UNIQUE_WEAPONS[89]
        raw, _ = writer.serialize(self.document, [Change('unique_weapon', 89, 'Owned', True)])
        document = parse_bytes(raw)
        row = fields(document.records('UniqueWeaponDataArray')[template['unique_save_index']])
        document = parse_bytes(edited_fixture_bytes(document, [(row['DataID'], struct.pack('<i', 12345))]))
        data_id = template['data_id']
        requests = [Change('unique_weapon', 89, 'Owned', True)]
        self.assertFalse(weapon.state(document, data_id, requests)['editable'])
        with self.assertRaises(SaveError):
            writer.serialize(document, requests + [Change('weapon_roll', data_id, 'Skills', weapon.original_skills(document, data_id))])

    def test_truncated_scalar_payload_returns_save_error(self):
        header = self.document.plaintext[4:self.document.parsed['properties'][0]['tag_offset']]
        for length in range(1, 17):
            tag = enum_bytes('X' * length) + enum_bytes('IntProperty') + struct.pack('<iiB', 0, 4, 0)
            payload = header + tag + b'12'
            if (len(payload) + 4) % 16 == 0:
                plain = struct.pack('>I', len(payload)) + payload
                break
        else:
            self.fail('No aligned test payload')
        with self.assertRaises(SaveError):
            parse_bytes(save_codec.encrypt(plain))

    def test_source_changed_during_serialization_is_not_overwritten(self):
        source = self.folder / 'input.sav'
        source.write_bytes(self.document.encrypted)
        document = read_save(source)
        concurrent, _ = writer.serialize(document, [Change('officer', 0, 'Attack', 149)])
        real = writer.serialize
        def concurrent_change(*args, **kwargs):
            result = real(*args, **kwargs)
            source.write_bytes(concurrent)
            return result
        with patch.object(writer, 'serialize', side_effect=concurrent_change), self.assertRaises(SaveError):
            writer.write_save(document, source, [Change('officer', 0, 'Attack', 150)], overwrite=True)
        self.assertEqual(source.read_bytes(), concurrent)
        self.assertFalse(list(self.folder.glob('*.changes.json')))
        self.assertFalse(list(self.folder.glob('.*.tmp')))

    def test_destination_created_during_serialization_is_preserved(self):
        destination = self.folder / 'output.sav'
        real = writer.serialize
        def concurrent_change(*args, **kwargs):
            result = real(*args, **kwargs)
            destination.write_bytes(b'Created by another process')
            return result
        with patch.object(writer, 'serialize', side_effect=concurrent_change), self.assertRaises(FileExistsError):
            writer.write_save(self.document, destination, overwrite=True)
        self.assertEqual(destination.read_bytes(), b'Created by another process')
        self.assertFalse(list(self.folder.glob('*.changes.json')))

    def test_backup_manifest_failure_keeps_completed_snapshot_and_existing_backup(self):
        self.folder.joinpath('existing.sav').write_bytes(b'Existing backup')
        real = writer._atomic_write
        def manifest_failure(data, path, *args, **kwargs):
            if Path(path).suffix == '.json':
                raise OSError('Injected manifest failure')
            return real(data, path, *args, **kwargs)
        with patch.object(writer, '_atomic_write', side_effect=manifest_failure), self.assertRaises(OSError):
            writer.backup_save(self.document, self.folder)
        snapshots = [path for path in self.folder.glob('*.sav') if path.name != 'existing.sav']
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].read_bytes(), self.document.encrypted)
        self.assertFalse(snapshots[0].with_suffix('.json').exists())
        self.assertEqual((self.folder / 'existing.sav').read_bytes(), b'Existing backup')

    def test_restore_manifest_is_bounded_and_validated(self):
        backup = writer.backup_save(self.document, self.folder)
        destination = self.folder / 'restored.sav'
        for metadata in ('[]', 'x' * 4097, '{'):
            backup.with_suffix('.json').write_text(metadata)
            with self.subTest(metadata=metadata[:10]), self.assertRaises(SaveError):
                writer.restore_backup(backup, destination)
            self.assertFalse(destination.exists())

    def test_restore_rejects_cloud_metadata_manifest_alias(self):
        backup = writer.backup_save(self.document, self.folder)
        manifest = backup.with_suffix('.json')
        real = Path.resolve
        def resolve(path, *args, **kwargs):
            if path == manifest:
                return Path('C:/review/steam_autocloud.vdf')
            return real(path, *args, **kwargs)
        with patch.object(Path, 'resolve', resolve), self.assertRaises(SaveError):
            writer.restore_backup(backup, self.folder / 'restored.sav')

    def test_destination_changed_during_temp_verification_is_preserved(self):
        source = self.folder / 'input.sav'
        source.write_bytes(self.document.encrypted)
        document = read_save(source)
        real = Path.read_bytes
        def concurrent_change(path):
            result = real(path)
            if path.name.startswith('.input.sav.') and path.name.endswith('.tmp'):
                source.write_bytes(b'Concurrent replacement during temporary verification')
            return result
        with patch.object(Path, 'read_bytes', concurrent_change), self.assertRaises(SaveError):
            writer.write_save(document, source, overwrite=True)
        self.assertEqual(source.read_bytes(), b'Concurrent replacement during temporary verification')
        self.assertFalse(list(self.folder.glob('.*.tmp')))


@unittest.skipUnless(FIXTURE.exists() and os.name == 'nt', 'Windows GUI and explicit private fixture required.')
class ReviewGuiTests(CopyTestCase):
    def setUp(self):
        super().setUp()
        import tkinter as tk
        import koei_editor.games.dw3.gui as gui
        self.gui = gui
        self.root = tk.Tk()
        self.root.withdraw()
        self.editor = gui.Editor(self.root)
        self.errors = []
        self.patches = [
            patch.object(gui.messagebox, 'showerror', side_effect=lambda *a, **kw: self.errors.append(a)),
            patch.object(gui.messagebox, 'askyesno', return_value=True),
        ]
        for mocked in self.patches:
            mocked.start()

    def tearDown(self):
        self.root.destroy()
        for mocked in reversed(self.patches):
            mocked.stop()
        super().tearDown()

    def open_copy(self, raw, name):
        source = self.folder / name
        source.write_bytes(raw)
        with patch.object(self.gui.filedialog, 'askopenfilename', return_value=str(source)):
            self.editor.open()
        return source

    def test_failed_open_keeps_previous_document_edits_and_backup(self):
        self.open_copy(self.document.encrypted, 'first.sav')
        self.editor.stage_many([Change('officer', 0, 'Attack', 150)])
        previous = self.editor.document, self.editor.backup, self.editor.changes.copy(), self.editor.history.copy()
        with patch.object(self.editor, 'refresh', side_effect=[RuntimeError('Injected display failure'), None]):
            self.open_copy(self.document.encrypted, 'second.sav')
        self.assertTrue(self.editor.document is previous[0], 'Previously opened document must survive a failed open.')
        self.assertEqual((self.editor.backup, self.editor.changes, self.editor.history), previous[1:])
        self.assertEqual(len(self.errors), 1)

    def test_unknown_bonus_opens_in_gui_as_view_only(self):
        row = fields(self.document.records('WeaponDataArray')[36])
        slot = fields(row['Skill']['value']['records'][0])
        raw = edited_fixture_bytes(self.document, [(slot['EquipItemID'], enum_bytes('EEquipItemID::EquipItemID_043'))])
        self.open_copy(raw, 'reserved.sav')
        self.assertFalse(self.errors)
        self.assertFalse(self.editor.weapon_rows['WeaponDataArray:36']['editable'])
        self.assertEqual(self.editor.document.encrypted, raw)


if __name__ == '__main__':
    unittest.main()
