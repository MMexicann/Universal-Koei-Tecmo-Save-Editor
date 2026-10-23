"""Report publication refuses aliases, races and invalid JSON without side effects."""
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.shared import report_export as reports
from koei_editor.shared import copy_storage
from koei_editor.games.dw3.models import SaveError


class ReportExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.destination = self.root / 'new.json'
        self.raw = b'{"read_only":true,"summary":"public facts"}\n'

    def test_exact_new_only_export_and_private_mode(self):
        self.assertEqual(reports.write_report_bytes(self.raw, self.destination), self.destination)
        self.assertEqual(self.destination.read_bytes(), self.raw)
        if os.name != 'nt':
            self.assertEqual(stat.S_IMODE(self.destination.stat().st_mode), 0o600)
        with self.assertRaises(FileExistsError):
            reports.write_report_bytes(b'{}', self.destination)
        self.assertEqual(self.destination.read_bytes(), self.raw)
        self.assertEqual([p.name for p in self.root.iterdir()], ['new.json'])

    def test_route_sized_report_over_64kib_is_not_truncated(self):
        raw = b'{"entries":"' + b'a' * 70_000 + b'"}'
        reports.write_report_bytes(raw, self.destination)
        self.assertEqual(self.destination.read_bytes(), raw)

    def test_invalid_or_oversized_json_is_rejected_before_publication(self):
        for raw in (b'', b'[]' * (reports.MAX_REPORT_BYTES // 2 + 1), b'not JSON',
                    b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b'42', b'[' * 66 + b'0' + b']' * 66,
                    bytearray(b'{}')):
            with self.subTest(kind=type(raw).__name__, length=len(raw)), \
                    patch.object(reports, 'publish_new_child_bound') as publish:
                with self.assertRaises(ValueError):
                    reports.write_report_bytes(raw, self.destination)
                publish.assert_not_called()
                self.assertFalse(self.destination.exists())

    def _link(self, link, target, directory=False):
        try:
            link.symlink_to(target, target_is_directory=directory)
        except OSError as error:
            self.skipTest('Host cannot create test symlinks: ' + type(error).__name__)

    def test_dangling_leaf_and_symlink_parent_are_never_followed(self):
        target = self.root / 'uncreated.json'
        self._link(self.destination, target)
        with self.assertRaises((ValueError, FileExistsError)):
            reports.write_report_bytes(self.raw, self.destination)
        self.assertTrue(self.destination.is_symlink())
        self.assertFalse(target.exists())
        self.destination.unlink()
        outside = self.root / 'outside'
        outside.mkdir()
        alias = self.root / 'alias'
        self._link(alias, outside, directory=True)
        with self.assertRaises(ValueError):
            reports.write_report_bytes(self.raw, alias / 'new.json')
        self.assertEqual(list(outside.iterdir()), [])

    def test_original_alias_dotdot_and_protected_dotdot_paths_are_refused(self):
        outside = self.root / 'elsewhere'
        target = outside / 'real'
        target.mkdir(parents=True)
        alias = self.root / 'alias'
        self._link(alias, target, directory=True)
        with self.assertRaises(ValueError):
            reports.write_report_bytes(self.raw, alias / '..' / 'new.json')
        self.assertFalse((self.root / 'new.json').exists())
        self.assertFalse((outside / 'new.json').exists())
        cloud = self.root / 'Steam' / 'userdata'
        cloud.mkdir(parents=True)
        with self.assertRaises(SaveError):
            reports.write_report_bytes(self.raw, cloud / '..' / 'new.json')
        self.assertFalse((cloud.parent / 'new.json').exists())
        ordinary = self.root / 'ordinary'
        ordinary.mkdir()
        if os.name == 'nt':
            # The shared Windows policy rejects trailing-dot path components,
            # including '..', before any normalization or publication.
            with self.assertRaises(SaveError):
                reports.write_report_bytes(b'{"n":1.5}', ordinary / '..' / 'new.json')
            self.assertFalse((self.root / 'new.json').exists())
        else:
            reports.write_report_bytes(b'{"n":1.5}', ordinary / '..' / 'new.json')
            self.assertEqual((self.root / 'new.json').read_bytes(), b'{"n":1.5}')

    def test_late_child_collision_preserves_foreign_bytes_and_uses_no_retry(self):
        original_publish = reports.publish_new_child_bound
        def occupy(raw, parent, name, identity):
            self.destination.write_bytes(b'FOREIGN_REPORT')
            return original_publish(raw, parent, name, identity)
        with patch.object(reports, 'publish_new_child_bound', side_effect=occupy) as publish:
            with self.assertRaises(FileExistsError):
                reports.write_report_bytes(self.raw, self.destination)
        self.assertEqual(publish.call_count, 1)
        self.assertEqual(self.destination.read_bytes(), b'FOREIGN_REPORT')
        self.assertEqual([p.name for p in self.root.iterdir()], ['new.json'])

    def test_changed_parent_identity_refuses_before_publication(self):
        folder = self.root / 'selected'
        folder.mkdir()
        moved = self.root / 'owned-before-change'
        destination = folder / 'new.json'
        original_publish = reports.publish_new_child_bound
        def substitute(raw, parent, name, identity):
            parent.rename(moved)
            parent.mkdir()
            return original_publish(raw, parent, name, identity)
        with patch.object(reports, 'publish_new_child_bound', side_effect=substitute):
            with self.assertRaises(SaveError):
                reports.write_report_bytes(self.raw, destination)
        self.assertEqual(list(folder.iterdir()), [])
        self.assertEqual(list(moved.iterdir()), [])

    def test_missing_parent_is_not_created_and_uncertain_failure_is_not_retried(self):
        with self.assertRaises(FileNotFoundError):
            reports.write_report_bytes(self.raw, self.root / 'missing' / 'new.json')
        self.assertFalse((self.root / 'missing').exists())
        with patch.object(reports, 'publish_new_child_bound', side_effect=SaveError('Uncertain publication')) as publish:
            with self.assertRaises(SaveError):
                reports.write_report_bytes(self.raw, self.destination)
        self.assertEqual(publish.call_count, 1)
        self.assertFalse(self.destination.exists())

    def test_unsupported_platform_fails_without_output(self):
        if os.name == 'nt':
            self.skipTest('Production Windows platform support is qualified by native CI')
        with patch.object(copy_storage.sys, 'platform', 'darwin'):
            with self.assertRaises(SaveError):
                reports.write_report_bytes(self.raw, self.destination)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_native_cleanup_forwarding_preserves_manifest_default(self):
        expected = self.destination
        with patch.object(copy_storage.os, 'name', 'nt'), \
                patch.object(copy_storage, 'Path', return_value=self.root), \
                patch.object(copy_storage, '_validate_child_name'), \
                patch.object(copy_storage, '_new_child_windows', return_value=expected) as native:
            copy_storage.publish_new_child_bound(self.raw, self.root, 'new.json', (1, 2))
            self.assertIs(native.call_args.kwargs['_cleanup_pending_on_failure'], False)
            copy_storage.publish_new_child_bound(self.raw, self.root, 'new.json', (1, 2),
                                                 cleanup_pending_on_failure=True)
            self.assertIs(native.call_args.kwargs['_cleanup_pending_on_failure'], True)
            self.assertEqual(native.call_args.kwargs['_publish_name'], 'new.json')

    @unittest.skipUnless(os.name == 'nt', 'Requires actual Windows native handle publication')
    def test_windows_confirmed_rejection_removes_only_owned_pending_child(self):
        with patch.object(copy_storage, '_rename_verified_child_windows', return_value=-1073741823):
            with self.assertRaises(SaveError):
                reports.write_report_bytes(self.raw, self.destination)
        self.assertEqual(list(self.root.iterdir()), [])

    @unittest.skipUnless(os.name == 'nt', 'Requires actual Windows native handle publication')
    def test_windows_uncertain_completed_rename_retains_exact_report_without_retry(self):
        rename = copy_storage._rename_verified_child_windows
        def complete_then_fail(ntdll, child, parent, name):
            status = rename(ntdll, child, parent, name)
            self.assertGreaterEqual(status, 0)
            raise OSError('Injected error after native publication')
        with patch.object(copy_storage, '_rename_verified_child_windows', side_effect=complete_then_fail) as native:
            with self.assertRaises(copy_storage.ChildPublishedUncertainError):
                reports.write_report_bytes(self.raw, self.destination)
        self.assertEqual(native.call_count, 1)
        self.assertEqual(self.destination.read_bytes(), self.raw)
        self.assertEqual([item.name for item in self.root.iterdir()], ['new.json'])


if __name__ == '__main__':
    unittest.main()
