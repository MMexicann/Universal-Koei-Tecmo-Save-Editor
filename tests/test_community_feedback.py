"""Allowlist boundaries prevent private diagnostics from entering review/export."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from koei_editor.shared.community_feedback import (
    build_bug_report, export_bug_report, import_bug_report, review_json,
)
from koei_editor.shared.validation_toolkit import ReportError, ValidationRecord


class CommunityFeedbackTests(unittest.TestCase):
    def test_empty_report_does_not_collect_environment_machine_or_save_details(self):
        with patch.dict('os.environ', {'HOME': '/private/example', 'TOKEN': 'secret-token'}):
            report = build_bug_report()
        content = review_json(report)
        self.assertEqual(report['diagnostics'], {})
        self.assertIsNone(report['game_id'])
        self.assertIsNone(report['validation'])
        self.assertEqual(report['transmission'], 'local_review_only')
        for sensitive in ('alice', 'secret-token', 'HOME', 'TOKEN', 'hostname', 'traceback', 'sha256'):
            self.assertNotIn(sensitive, content)

    def test_only_allowlisted_diagnostics_survive_roundtrip(self):
        report = build_bug_report(game_id='dw8xl', category='compatibility',
                                  error_code='input_rejected', locale='de',
                                  diagnostics={'os_family': 'windows', 'ui_scale': '150', 'theme': 'dark'})
        self.assertEqual(import_bug_report(review_json(report)), report)
        self.assertEqual(report['platform'], 'Windows PC')

    def test_legacy_report_and_nested_validation_migrate_without_promoting_claims(self):
        validation = ValidationRecord.create('dw8xl', provenance='genuine_file')
        current = build_bug_report(game_id='dw8xl', validation=validation)
        self.assertEqual(current['app_version'], '3.1')
        legacy = json.loads(json.dumps(current))
        legacy['app_version'] = '2.7'
        legacy['validation']['app_version'] = '2.7'
        imported = import_bug_report(json.dumps(legacy))
        self.assertEqual(imported, current)
        self.assertEqual(imported['validation']['attestation'], 'user_reported_unverified')
        self.assertEqual(set(imported['validation']['steps'].values()), {'not_run'})

    def test_unknown_keys_rejected_without_echo(self):
        for key in ('path', 'account_id', 'environment', 'stack', 'save_contents', 'notes', 'email', 'hostname'):
            with self.subTest(key=key), self.assertRaises(ReportError) as caught:
                build_bug_report(diagnostics={key: '/private/example/private.sav'})
            self.assertNotIn('alice', str(caught.exception))

    def test_allowed_keys_reject_private_or_wrong_type_values(self):
        for key in ('os_family', 'ui_scale', 'theme'):
            for value in ('/private/example/private.sav', {'secret': 'data'}, ['windows'], True, 150, None):
                with self.subTest(key=key, value=value), self.assertRaises(ReportError):
                    build_bug_report(diagnostics={key: value})
        for diagnostics in ([], (), 'alice', True):
            with self.subTest(diagnostics=diagnostics), self.assertRaises(ReportError):
                build_bug_report(diagnostics=diagnostics)

    def test_controlled_symptoms_cannot_carry_exception_text(self):
        for key in ('category', 'error_code', 'locale', 'game_id'):
            with self.subTest(key=key), self.assertRaises(ReportError):
                build_bug_report(**{key: 'PermissionError /private/example/private.sav'})

    def test_validation_requires_matching_explicit_profile(self):
        validation = ValidationRecord.create('dw8xl', provenance='genuine_file')
        for game_id in (None, 'dw3'):
            with self.subTest(game_id=game_id), self.assertRaises(ReportError):
                build_bug_report(game_id=game_id, validation=validation)
        with self.assertRaises(ReportError):
            build_bug_report(game_id='dw8xl', validation=validation.to_dict())
        report = build_bug_report(game_id='dw8xl', validation=validation)
        self.assertEqual(import_bug_report(review_json(report)), report)
        self.assertEqual(report['validation']['attestation'], 'user_reported_unverified')

    def test_mutating_reviewed_dict_cannot_bypass_export_allowlist(self):
        for mutation in ({'path': '/private/example/private.sav'}, {'platform': 'PlayStation 3'},
                         {'diagnostics': {'notes': 'secret'}}, {'transmission': 'upload'},
                         {'schema_version': True}, {'app_version': '2.8'}):
            report = build_bug_report()
            report.update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(ReportError):
                review_json(report)

    def test_import_rejects_duplicate_nested_keys_and_oversize(self):
        content = review_json(build_bug_report())
        malformed = content.replace('"diagnostics": {}', '"diagnostics": {"theme":"light","theme":"dark"}')
        for data in (malformed, ' ' * 16385, '{"kind":"community_bug_report"}', 'null', '[]'):
            with self.subTest(data=data[:60]), self.assertRaises(ReportError):
                import_bug_report(data)

    def test_export_is_local_and_exclusive_and_revalidates(self):
        report = build_bug_report(locale='de')
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'feedback.json'
            with patch('socket.create_connection', side_effect=AssertionError('No network')):
                export_bug_report(report, destination)
            raw = destination.read_text(encoding='utf-8')
            self.assertEqual(import_bug_report(raw), report)
            self.assertNotIn(folder, raw)
            with self.assertRaises(FileExistsError):
                export_bug_report(report, destination)
            report['notes'] = 'private'
            with self.assertRaises(ReportError):
                export_bug_report(report, Path(folder) / 'bad.json')
            self.assertFalse((Path(folder) / 'bad.json').exists())


if __name__ == '__main__':
    unittest.main()
