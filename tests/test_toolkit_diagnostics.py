"""Path-free runtime reports and exclusive, alias-safe local exports."""
import copy
from importlib import metadata
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.shared import toolkit_diagnostics as diagnostics
from koei_editor.shared import report_export


class DiagnosticsTests(unittest.TestCase):
    def test_report_catalog_and_limits_are_actual_and_do_not_claim_game_validation(self):
        from koei_editor.supported_games import SUPPORTED_GAMES
        from koei_editor.conversion import ROUTES
        report = diagnostics.collect_diagnostics('1.0')
        self.assertEqual(report['catalog']['profiles'], len(SUPPORTED_GAMES))
        self.assertEqual(report['catalog']['platforms'], len({g.platform for g in SUPPORTED_GAMES}))
        self.assertEqual(report['catalog']['conversion_routes'], len(ROUTES))
        self.assertIs(report['catalog']['in_game_verified'], False)
        self.assertEqual(report['application']['version'], '1.0')
        self.assertIn('does not verify native decoders', ' '.join(report['limitations']))
        self.assertEqual(json.loads(diagnostics.report_json(report)), report)
        self.assertLess(len(diagnostics.report_json(report)), diagnostics.MAX_REPORT_BYTES)

    def test_metadata_errors_custom_versions_architecture_and_environment_do_not_leak(self):
        sentinel = 'PRIVATE_SUPPORT_SENTINEL'
        values = ['1.71', '5.1.1+' + sentinel, metadata.PackageNotFoundError(sentinel),
                  OSError(sentinel), '2.1/' + sentinel]
        def version(_name):
            value = values.pop(0)
            if isinstance(value, Exception):
                raise value
            return value
        with patch.object(diagnostics.metadata, 'version', side_effect=version), \
                patch.object(diagnostics.platform, 'machine', return_value=sentinel), \
                patch.dict(os.environ, {'USER': sentinel, 'HOME': sentinel, 'USERNAME': sentinel}):
            report = diagnostics.collect_diagnostics('1.0')
        encoded = diagnostics.report_json(report)
        self.assertNotIn(sentinel, encoded)
        self.assertEqual(report['runtime']['architecture'], 'other')
        self.assertEqual([item['status'] for item in report['dependencies']],
                         ['metadata_available', 'version_unrecognized', 'not_installed', 'unavailable', 'version_unrecognized'])
        with patch.object(diagnostics.platform, 'machine', side_effect=RuntimeError(sentinel)):
            self.assertEqual(diagnostics.collect_diagnostics('1.0')['runtime']['architecture'], 'other')
        with patch.object(diagnostics.metadata, 'version') as query:
            with self.assertRaises(ValueError) as error:
                diagnostics.collect_diagnostics('1.0+' + sentinel)
        query.assert_not_called()
        self.assertNotIn(sentinel, str(error.exception))

    def test_platform_capability_is_limited_and_frozen_mode_is_explicit(self):
        for system, platform, expected in (('nt', 'win32', True), ('posix', 'linux', False), ('posix', 'darwin', False)):
            with self.subTest(platform=platform), patch.object(diagnostics.os, 'name', system), \
                    patch.object(diagnostics.sys, 'platform', platform), \
                    patch.object(diagnostics.sys, 'frozen', True, create=True):
                report = diagnostics.collect_diagnostics('1.0')
            self.assertEqual(report['application']['mode'], 'frozen')
            item = report['capabilities']['save_vault_profiles']
            self.assertEqual(item['supported_platform'], expected)
            self.assertEqual(item['status'], 'destination_checks_required' if expected else 'requires_windows')

    def test_arbitrary_fields_private_values_and_false_certification_are_refused(self):
        original = diagnostics.collect_diagnostics('1.0')
        for mutation in (
                lambda x: x.update({'log': 'PRIVATE_SUPPORT_SENTINEL'}),
                lambda x: x['runtime'].update({'path': 'PRIVATE_SUPPORT_SENTINEL'}),
                lambda x: x['dependencies'][0].update(version='1.0+PRIVATE_SUPPORT_SENTINEL', status='metadata_available'),
                lambda x: x['catalog'].update(in_game_verified=True),
                lambda x: x['limitations'].append('PRIVATE_SUPPORT_SENTINEL')):
            report = copy.deepcopy(original)
            mutation(report)
            with self.assertRaises(ValueError):
                diagnostics.report_json(report)

    def test_new_report_is_exact_private_and_existing_files_are_preserved(self):
        report = diagnostics.collect_diagnostics('1.0')
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'support.json'
            diagnostics.export_report(report, destination)
            self.assertEqual(destination.read_bytes(), diagnostics.report_json(report).encode('ascii'))
            if os.name != 'nt':
                self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
            original = destination.read_bytes()
            with self.assertRaises(FileExistsError):
                diagnostics.export_report(report, destination)
            self.assertEqual(destination.read_bytes(), original)
            self.assertEqual({x.name for x in Path(folder).iterdir()}, {'support.json'})

    def test_dangling_selected_link_never_creates_its_target(self):
        report = diagnostics.collect_diagnostics('1.0')
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'selected.json'
            target = Path(folder) / 'must-not-exist.json'
            try:
                destination.symlink_to(target)
            except OSError as error:
                self.skipTest('Host cannot create a test symlink: ' + type(error).__name__)
            with self.assertRaises((ValueError, FileExistsError)):
                diagnostics.export_report(report, destination)
            self.assertTrue(destination.is_symlink())
            self.assertFalse(target.exists())

    def test_new_report_refuses_a_late_child_alias_without_following_it(self):
        report = diagnostics.collect_diagnostics('1.0')
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'selected.json'
            target = Path(folder) / 'untouched.json'
            target.write_bytes(b'FOREIGN_RECORD')
            original_publish = report_export.publish_new_child_bound
            def substitute(raw, parent, name, identity):
                try:
                    destination.symlink_to(target)
                except OSError as error:
                    self.skipTest('Host cannot create a test symlink: ' + type(error).__name__)
                return original_publish(raw, parent, name, identity)
            with patch.object(report_export, 'publish_new_child_bound', side_effect=substitute):
                with self.assertRaises(FileExistsError):
                    diagnostics.export_report(report, destination)
            self.assertTrue(destination.is_symlink())
            self.assertEqual(target.read_bytes(), b'FOREIGN_RECORD')

    def test_backend_collects_without_a_display_or_tk_import(self):
        environment = os.environ.copy()
        environment.pop('DISPLAY', None)
        code = ('import sys; from koei_editor.shared.toolkit_diagnostics import collect_diagnostics, report_json; '
                'print(report_json(collect_diagnostics("1.0"))); '
                'assert "tkinter" not in sys.modules')
        result = subprocess.run([sys.executable, '-c', code], env=environment, text=True,
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['application']['version'], '1.0')


if __name__ == '__main__':
    unittest.main()
