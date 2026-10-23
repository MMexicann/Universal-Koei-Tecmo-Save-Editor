"""Game Hub ordering, snapshot privacy and explicit new-file report exports."""
from dataclasses import replace
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.shared import game_hub_reports as reports
from koei_editor.shared.save_discovery import DiscoveryResult, InstalledGame, STEAM_MAPPINGS


class HubInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.installed = InstalledGame(
            'atelier_sophie', '527270', self.folder / 'SYNTHETIC_PRIVATE_INSTALL',
            library_path=self.folder / 'SYNTHETIC_PRIVATE_LIBRARY', build_id='10',
            last_updated='1700000000', size_on_disk=2000,
            evidence='SYNTHETIC_PRIVATE_EVIDENCE')
        self.snapshot = DiscoveryResult((self.installed,), (), ('SYNTHETIC_PRIVATE_ISSUE',),
                                        'complete', 10, 200, ('atelier_sophie',))

    def test_numeric_ordering_unknowns_and_ties_are_stable_in_both_directions(self):
        def row(identity, title, build, size, timestamp):
            return (identity, title, 'Installed', replace(
                self.installed, build_id=build, size_on_disk=size, last_updated=timestamp), '')
        rows = [row('b', 'Beta', '10', 2000, '1700000000'),
                row('a', 'Alpha', '2', 900, '1600000000'),
                row('d', 'Delta', None, None, None),
                row('c', 'Charlie', '10', 2000, '1700000000'),
                ('e', 'Echo', 'Not detected', None, '')]
        original = list(rows)
        for column in ('build', 'size', 'updated'):
            with self.subTest(column=column):
                self.assertEqual([row[0] for row in reports.sort_rows(rows, column)],
                                 ['a', 'b', 'c', 'd', 'e'])
                self.assertEqual([row[0] for row in reports.sort_rows(rows, column, True)],
                                 ['b', 'c', 'a', 'd', 'e'])
        self.assertEqual(rows, original)

    def test_invalid_numeric_markers_stay_unknown_without_boolean_coercion(self):
        good = ('a', 'Alpha', 'Installed', self.installed, '')
        bad = ('b', 'Beta', 'Installed', replace(self.installed, build_id='private',
                                                 size_on_disk=True,
                                                 last_updated='999999999999'), '')
        for column in ('build', 'size', 'updated'):
            self.assertEqual([r[0] for r in reports.sort_rows([bad, good], column, True)], ['a', 'b'])
        with self.assertRaises(ValueError):
            reports.sort_rows([good], 'unreviewed')

    def test_report_is_canonical_path_free_and_never_serializes_external_strings(self):
        unsafe = replace(self.installed, build_id='SYNTHETIC_PRIVATE_BUILD',
                         last_updated='SYNTHETIC_PRIVATE_TIME', size_on_disk=-5,
                         source='SYNTHETIC_PRIVATE_SOURCE', confidence='SYNTHETIC_PRIVATE_CONFIDENCE')
        snapshot = replace(self.snapshot, installed_games=(unsafe,),
                           stop_reason='SYNTHETIC_PRIVATE_STOP')
        result = reports.inventory_report(snapshot, ('527270:0',))
        raw = json.dumps(result)
        self.assertNotIn('SYNTHETIC_PRIVATE', raw)
        self.assertNotIn(str(self.folder), raw)
        self.assertFalse(result['contains_paths'])
        self.assertFalse(result['contains_local_notes'])
        self.assertEqual(result['scan'], {'state': 'partial', 'stop_reason': 'unknown',
                                         'refresh_failed': False, 'previous_results': False,
                                         'issue_count': 1})
        game = result['games'][0]
        self.assertEqual(game['game_id'], 'atelier_sophie')
        self.assertIn('sophie', game['title'].casefold())
        self.assertIsNone(game['build_id'])
        self.assertIsNone(game['last_updated_unix'])
        self.assertIsNone(game['size_on_disk'])

    def test_unscanned_partial_complete_and_refresh_failure_remain_distinct(self):
        unscanned = reports.inventory_report()
        self.assertEqual(unscanned['scan']['state'], 'not_scanned')
        self.assertTrue(all(row['installation'] == 'not_scanned' for row in unscanned['games']))
        for stop in ('cancelled', 'entry_limit', 'byte_limit', 'root_limit', 'result_limit'):
            result = reports.inventory_report(replace(self.snapshot, stop_reason=stop))
            missing = [row for row in result['games'] if row['installation'] != 'detected']
            self.assertEqual(result['scan']['state'], 'partial')
            self.assertTrue(all(row['installation'] == 'not_detected_partial' for row in missing))
        previous = reports.inventory_report(self.snapshot, refresh_failed=True)
        self.assertEqual(previous['scan']['state'], 'complete')
        self.assertTrue(previous['scan']['refresh_failed'])
        self.assertTrue(previous['scan']['previous_results'])
        self.assertEqual(previous['coverage']['tracked_profile_count'], len(STEAM_MAPPINGS))
        self.assertEqual(previous['coverage']['detected_installation_count'], 1)

    def test_visible_export_scope_and_order_are_exact_even_when_empty(self):
        full = reports.inventory_report(self.snapshot)
        ids = tuple('527270:0' if row['steam_app_id'] == '527270' else
                    row['steam_app_id'] + ':missing' for row in full['games'])
        selected = reports.inventory_report(self.snapshot, (ids[2], ids[0]))
        self.assertEqual(selected['scope'], 'visible_rows')
        self.assertEqual([row['steam_app_id'] for row in selected['games']],
                         [ids[2].split(':')[0], ids[0].split(':')[0]])
        self.assertEqual(selected['coverage']['visible_row_count'], 2)
        self.assertEqual(reports.inventory_report(self.snapshot, ())['games'], [])
        for bad in (('unknown:0',), ('527270:0', '527270:0'), '527270:0', iter(ids)):
            with self.subTest(bad=type(bad).__name__), self.assertRaises(ValueError):
                reports.inventory_report(self.snapshot, bad)

    def test_invalid_or_oversized_snapshots_reject_before_export(self):
        for snapshot in (replace(self.snapshot, installed_games=(replace(self.installed, app_id='999999'),)),
                         replace(self.snapshot, installed_games=(replace(self.installed, game_id='dw8xl'),)),
                         replace(self.snapshot, installed_games=(self.installed,) * 501),
                         replace(self.snapshot, issues=('issue',) * 2001)):
            with self.subTest(count=len(snapshot.installed_games)), self.assertRaises(ValueError):
                reports.export_inventory(self.folder / 'must-not-exist.json', snapshot)
        self.assertEqual(list(self.folder.iterdir()), [])

    @unittest.skipUnless(os.name == 'nt' or os.sys.platform.startswith('linux'),
                         'Native new-file publication is supported on Windows and Linux')
    def test_export_is_new_only_private_and_preserves_original_and_prior_reports(self):
        original = self.folder / 'original-manifest.acf'
        original.write_bytes(b'SYNTHETIC_PRIVATE_MANIFEST')
        destination = self.folder / 'report.json'
        reports.export_inventory(destination, self.snapshot, ('527270:0',))
        raw = destination.read_bytes()
        self.assertEqual(json.loads(raw)['coverage']['visible_row_count'], 1)
        if os.name == 'posix':
            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
        with self.assertRaises(FileExistsError):
            reports.export_inventory(destination, self.snapshot, ())
        self.assertEqual(destination.read_bytes(), raw)
        self.assertEqual(original.read_bytes(), b'SYNTHETIC_PRIVATE_MANIFEST')
        self.assertEqual({p.name for p in self.folder.iterdir()}, {'report.json', original.name})

    def test_size_bound_is_checked_before_any_write(self):
        with patch.object(reports, 'MAX_REPORT_BYTES', 1), patch.object(reports, 'write_report_bytes') as writer:
            with self.assertRaises(ValueError):
                reports.export_inventory(self.folder / 'report.json', self.snapshot)
        writer.assert_not_called()

    def test_dangling_report_alias_cannot_redirect_new_report_creation(self):
        target = self.folder / 'must-not-be-created.json'
        alias = self.folder / 'selected-report.json'
        try:
            alias.symlink_to(target)
        except OSError as error:
            self.skipTest(f'Host cannot create a test symlink: {error}')
        with self.assertRaises((ValueError, FileExistsError)):
            reports.export_inventory(alias, self.snapshot)
        self.assertTrue(alias.is_symlink())
        self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
