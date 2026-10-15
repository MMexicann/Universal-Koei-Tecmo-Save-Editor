"""Synthetic opaque artifacts test copy safety; they are not Origins save fixtures."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
import koei_editor.games.origins.origins_editor as origins
import koei_editor.shared.copy_storage as copy_storage
from koei_editor.game_registry import get_game
from koei_editor.games.dw3.models import SaveError, Change
from koei_editor.shared.save_safety import safe_path


class OriginsCopyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.source = self.folder / 'SLOT0001.dat'
        self.raw = bytes(range(256)) * 4
        self.source.write_bytes(self.raw)
        self.document = origins.inspect_copy(self.source)

    def tearDown(self):
        self.temp.cleanup()

    def test_artifact_inspection_never_claims_gameplay_identity(self):
        self.assertEqual(self.document.sha256, hashlib.sha256(self.raw).hexdigest())
        self.assertIsNone(self.document.reference)
        self.assertFalse(self.document.editable)
        with self.assertRaises(SaveError):
            origins.parse_bytes(self.raw)
        with self.assertRaises(SaveError):
            origins.read_save(self.source)
        for changes in ([], [Change('resources', 0, 'Money', 99999)]):
            with self.assertRaises(SaveError):
                origins.serialize(self.document, changes)

    def test_corrupt_truncated_oversized_and_wrong_game_inputs_rejected(self):
        for raw in (b'', b'x', bytes(32), b'GVAS' + self.raw, b'ABCDGVAS' + self.raw):
            with self.subTest(raw=raw[:8]), self.assertRaises(SaveError):
                origins.inspect_bytes(raw)
        with patch.object(origins, 'MAX_SIZE', 32):
            with self.assertRaises(SaveError):
                origins.inspect_copy(self.source)
        dw3 = self.folder / 'GameStatusData.sav'
        dw3.write_bytes(self.raw)
        with self.assertRaises(SaveError):
            origins.inspect_copy(dw3)
        with patch('koei_editor.games.dw3.save_parser.read_save') as dw3_reader:
            with self.assertRaises(SaveError):
                get_game('dw3').read_save(self.source)
            dw3_reader.assert_not_called()
        with patch('koei_editor.games.origins.origins_parser.read_save') as origins_reader:
            with self.assertRaises(SaveError):
                get_game('origins').read_save(dw3)
            origins_reader.assert_not_called()

    def test_backup_restore_copy_and_source_preservation(self):
        backup = origins.backup_copy(self.document)
        restored = origins.restore_backup(backup, self.folder / 'restored.dat')
        duplicate = origins.duplicate_copy(self.document, self.folder / 'copy.dat')
        for path in (backup, restored, duplicate, self.source):
            self.assertEqual(path.read_bytes(), self.raw)
        manifest = json.loads(backup.with_suffix('.json').read_text())
        self.assertEqual(manifest['game_id'], 'origins')
        self.assertEqual(manifest['sha256'], self.document.sha256)
        with self.assertRaises(FileExistsError):
            origins.duplicate_copy(self.document, duplicate)
        with self.assertRaises(FileExistsError):
            origins.restore_backup(backup, restored)
        self.assertEqual(duplicate.read_bytes(), self.raw)

    def test_restore_requires_matching_game_manifest_hash_and_size(self):
        backup = origins.backup_copy(self.document)
        manifest_path = backup.with_suffix('.json')
        original = json.loads(manifest_path.read_text())
        for field, value in (('game_id', 'dw3'), ('sha256', '0' * 64), ('size_bytes', 1), ('kind', 'edited')):
            manifest = dict(original, **{field: value})
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaises(SaveError):
                origins.restore_backup(backup, self.folder / 'bad.dat')
            self.assertFalse((self.folder / 'bad.dat').exists())
        manifest_path.write_text(json.dumps(original))
        backup.write_bytes(b'damaged data 12345')
        with self.assertRaises(SaveError):
            origins.restore_backup(backup, self.folder / 'bad.dat')

    def test_external_source_change_prevents_copying_stale_state(self):
        self.source.write_bytes(self.raw + b'changed')
        with self.assertRaises(SaveError):
            origins.duplicate_copy(self.document, self.folder / 'stale.dat')
        self.assertFalse((self.folder / 'stale.dat').exists())

    def test_backup_manifest_failure_retains_completed_snapshot(self):
        original = copy_storage.atomic_new
        def injected(data, destination):
            if Path(destination).suffix == '.json':
                raise OSError('Simulated manifest failure')
            return original(data, destination)
        with patch.object(copy_storage, 'atomic_new', side_effect=injected):
            with self.assertRaises(OSError):
                origins.backup_copy(self.document)
        snapshots = list((self.folder / 'OriginsEditorBackups').glob('*.dat'))
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0].read_bytes(), self.raw)
        # An incomplete backup cannot be restored without its hash manifest.
        with self.assertRaises((OSError, SaveError)):
            origins.restore_backup(snapshots[0], self.folder / 'incomplete.dat')
        self.assertFalse((self.folder / 'incomplete.dat').exists())
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_racing_destination_creation_is_never_overwritten(self):
        destination = self.folder / 'race.dat'
        if copy_storage.os.name == 'nt':
            target, original = 'rename', copy_storage.os.rename
        else:
            target, original = 'link', copy_storage.os.link
        def race(source, dest):
            Path(dest).write_bytes(b'other editor data')
            return original(source, dest)
        with patch.object(copy_storage.os, target, side_effect=race):
            with self.assertRaises(FileExistsError):
                origins.duplicate_copy(self.document, destination)
        self.assertEqual(destination.read_bytes(), b'other editor data')
        self.assertFalse(list(self.folder.glob('.*.tmp')))

    def test_comparison_counts_bytes_ranges_and_resizing_without_inferring_fields(self):
        after = bytearray(self.raw)
        after[3:6] = b'abc'
        after[50] ^= 1
        report = origins.compare_copies(self.document, origins.inspect_bytes(bytes(after) + b'xyz'))
        self.assertEqual(report['changed_bytes'], 7)
        self.assertEqual(report['ranges'], [{'offset': 3, 'length': 3}, {'offset': 50, 'length': 1},
                                           {'offset': len(self.raw), 'length': 3}])
        self.assertEqual(report['changed_range_count'], 3)
        self.assertFalse(report['ranges_truncated'])
        self.assertEqual(origins.compare_copies(self.document, self.document)['changed_bytes'], 0)
        report = origins.compare_copies(self.document, origins.inspect_bytes(bytes(after)), limit=1)
        self.assertTrue(report['ranges_truncated'])
        self.assertEqual(report['changed_range_count'], 2)
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_comparison_report_excludes_payloads_and_absolute_paths(self):
        report = origins.compare_copies(self.document, self.document)
        result = origins.export_comparison(report, self.folder / 'private.changes.json')
        text = result.read_text()
        self.assertNotIn(str(self.folder), text)
        self.assertNotIn('before_hex', text)
        with self.assertRaises(SaveError):
            origins.export_comparison(report, self.folder / 'report.json')

    def test_live_paths_cloud_metadata_and_symlink_aliases_are_rejected(self):
        for path in (r'C:\Users\Player\AppData\Local\KoeiTecmo\Dynasty Warriors Origins\Savedata\123\SLOT0000.dat',
                     r'C:\Users\Player\AppData\Local\KoeiTecmo\DW3CE_RE\Saved\SaveGames\GameStatusData.sav',
                     r'C:\Steam\userdata\123\456\remote\SLOT0000.dat', r'C:\a\steam_autocloud.vdf'):
            with self.subTest(path=path), self.assertRaises(SaveError):
                safe_path(path)
        live = self.folder / 'KoeiTecmo/Dynasty Warriors Origins/Savedata/123/SLOT0000.dat'
        live.parent.mkdir(parents=True)
        live.write_bytes(self.raw)
        alias = self.folder / 'alias.dat'
        try:
            alias.symlink_to(live)
        except OSError:
            return  # Some Windows test users cannot create symbolic links.
        with self.assertRaises(SaveError):
            origins.inspect_copy(alias)

    def test_registered_game_rejects_unknown_identity(self):
        with self.assertRaises(SaveError):
            get_game('other')

    def test_exact_fingerprint_recognition_does_not_enable_editing(self):
        evidence = {'references': [{'bytes': len(self.raw), 'sha256': self.document.sha256}]}
        with patch.object(origins, 'EVIDENCE', evidence):
            document = origins.parse_bytes(self.raw)
            self.assertIsNotNone(document.reference)
            self.assertFalse(document.editable)
            with self.assertRaises(SaveError):
                origins.parse_bytes(self.raw[:-1] + bytes([self.raw[-1] ^ 1]))
            with self.assertRaises(SaveError):
                origins.serialize(document, [])


if __name__ == '__main__':
    unittest.main()
