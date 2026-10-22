"""Path-free JSON reports from the offline community package checker."""
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from koei_editor.shared import community_packages
from tools import check_community_packages as checker


def sample_package():
    return community_packages.loads(json.dumps({
        'schema': community_packages.SCHEMA,
        'version': community_packages.SCHEMA_VERSION,
        'kind': 'character_build',
        'id': 'community.sample-build',
        'title': 'Example build',
        'author': 'Example author',
        'game_id': 'dw8xl',
        'platform': 'pc',
        'game_version': None,
        'description': 'Fictional test metadata.',
        'payload': {
            'character_id': 'officer.example', 'level': 10,
            'stats': [{'key': 'attack', 'value': 20}],
            'skills': [], 'equipment': [],
        },
    }, allow_nan=False).encode('utf-8'))


class CommunityPackageReportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def test_valid_report_is_versioned_json_and_states_its_scope(self):
        (self.directory / ('sample' + community_packages.SUFFIX)).write_bytes(
            community_packages.dumps(sample_package()))
        report = checker.validate_directory(self.directory)
        self.assertEqual(report['schema'], checker.REPORT_SCHEMA)
        self.assertEqual(report['version'], checker.REPORT_VERSION)
        self.assertEqual(report['validation_scope'], 'package_structure_only')
        self.assertTrue(report['valid'])
        self.assertEqual(report['summary'], {'checked': 1, 'valid': 1, 'invalid': 0})
        self.assertEqual(report['results'][0]['kind'], 'character_build')
        self.assertEqual(report['results'][0]['package_id'], 'community.sample-build')
        self.assertIn('host_checks_required', {item['code'] for item in report['results'][0]['warnings']})

    def test_mixed_results_are_machine_readable_and_do_not_emit_directory_paths(self):
        valid_name = 'sample' + community_packages.SUFFIX
        (self.directory / valid_name).write_bytes(community_packages.dumps(sample_package()))
        invalid_name = 'invalid' + community_packages.SUFFIX
        (self.directory / invalid_name).write_bytes(b'{"private":"not exposed"}')
        report = checker.validate_directory(self.directory)
        encoded = json.dumps(report, ensure_ascii=True)
        self.assertFalse(report['valid'])
        self.assertEqual(report['summary'], {'checked': 2, 'valid': 1, 'invalid': 1})
        self.assertNotIn(str(self.directory), encoded)
        self.assertNotIn('not exposed', encoded)
        invalid = next(item for item in report['results'] if item['file_index'] == 1)
        self.assertNotIn(valid_name, encoded)
        self.assertNotIn(invalid_name, encoded)
        self.assertEqual(invalid['errors'][0]['code'], 'invalid_package')

    def test_reports_omit_user_supplied_filenames_and_path_controls(self):
        name = 'private-owner\u202e' + community_packages.SUFFIX
        (self.directory / name).write_bytes(community_packages.dumps(sample_package()))
        report = checker.validate_directory(self.directory)
        encoded = json.dumps(report, ensure_ascii=True)
        self.assertEqual(report['results'][0]['file_index'], 1)
        self.assertNotIn('private-owner', encoded)
        self.assertNotIn('\u202e', encoded)

    def test_discovery_is_shallow_and_empty_or_unavailable_folders_fail(self):
        child = self.directory / 'nested'
        child.mkdir()
        (child / ('sample' + community_packages.SUFFIX)).write_bytes(
            community_packages.dumps(sample_package()))
        empty = checker.validate_directory(self.directory)
        self.assertFalse(empty['valid'])
        self.assertEqual(empty['errors'][0]['code'], 'no_packages_found')
        not_directory = checker.validate_directory(self.directory / 'missing')
        self.assertFalse(not_directory['valid'])
        self.assertEqual(not_directory['errors'][0]['code'], 'directory_unavailable')

    def test_bounded_directory_discovery_and_symlink_directory_rejection(self):
        with patch.object(checker, 'MAX_DIRECTORY_ENTRIES', 1):
            (self.directory / 'ordinary.txt').write_text('ok', encoding='utf-8')
            (self.directory / ('sample' + community_packages.SUFFIX)).write_bytes(
                community_packages.dumps(sample_package()))
            report = checker.validate_directory(self.directory)
            self.assertFalse(report['valid'])
            self.assertEqual(report['errors'][0]['code'], 'directory_unavailable')

        link = self.directory / 'directory-link'
        try:
            link.symlink_to(self.directory, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('Symlink creation is unavailable on this platform.')
        report = checker.validate_directory(link)
        self.assertFalse(report['valid'])
        self.assertEqual(report['errors'][0]['code'], 'directory_unavailable')

    def test_cli_prints_json_and_returns_validation_status(self):
        package_path = self.directory / ('sample' + community_packages.SUFFIX)
        package_path.write_bytes(community_packages.dumps(sample_package()))
        output = StringIO()
        with redirect_stdout(output):
            status = checker.main([str(self.directory)])
        self.assertEqual(status, 0)
        self.assertTrue(json.loads(output.getvalue())['valid'])

        package_path.write_bytes(b'bad input')
        output = StringIO()
        with redirect_stdout(output):
            status = checker.main([str(self.directory)])
        self.assertEqual(status, 1)
        self.assertFalse(json.loads(output.getvalue())['valid'])


if __name__ == '__main__':
    unittest.main()
